import logging
import re
import time

from crewai import Agent, Task, Crew, Process, LLM
from django.conf import settings

from safety.ai_utils.rag_system import get_rag
from safety.ai_utils.tools import openai_client, safety_image_tool, SAFEGUARD_IMAGE_URL_PREFIX

logger = logging.getLogger('safety')


def _get_topic_hints():
    return settings.SAFEGUARDAI['TOPIC_REQUIRED_SOURCE_HINTS'] or ()


def _query_expects_topic_not_in_sources(query: str, sources: list) -> bool:
    q = query.lower()
    source_names_lower = ' '.join(s.lower() for s in sources)
    for keywords, required_in_source in _get_topic_hints():
        if not any(kw in q for kw in keywords):
            continue
        if any(hint in source_names_lower for hint in required_in_source):
            continue
        return True
    return False


def _get_image_trigger_phrases():
    return tuple(settings.SAFEGUARDAI['IMAGE_TRIGGER_PHRASES'])


def _user_asked_for_image(query: str) -> bool:
    q = query.lower().strip()
    return any(phrase in q for phrase in _get_image_trigger_phrases())


def _description_for_image(query: str) -> str:
    cfg = settings.SAFEGUARDAI
    max_len = cfg['IMAGE_DESCRIPTION_MAX_LENGTH']
    fallback = cfg['IMAGE_DESCRIPTION_FALLBACK']
    phrases = _get_image_trigger_phrases()
    q = query.strip()
    lower = q.lower()
    for phrase in phrases:
        if phrase in lower:
            idx = lower.find(phrase)
            after = q[idx + len(phrase):].strip()
            for lead in ('of ', 'a ', 'an ', 'the '):
                if after.lower().startswith(lead):
                    after = after[len(lead):].strip()
                    break
            if after:
                q = after
                break
    if len(q) > max_len:
        q = q[: max_len - 3].rsplit(' ', 1)[0] + '...' if ' ' in q[: max_len - 3] else q[:max_len]
    return q or fallback


def _get_not_in_docs_message():
    return settings.SAFEGUARDAI['NOT_IN_DOCUMENTS_MESSAGE']


def _classify_not_in_docs_reply(answer: str, not_in_docs_msg: str) -> tuple[bool, bool]:
    """Return (replace_with_fallback, omit_sources). Used to normalise answer and avoid appending sources to fallback."""
    an = re.sub(r'\s+', ' ', answer.strip()).lower()
    nn = re.sub(r'\s+', ' ', not_in_docs_msg.strip()).lower()
    exact = an == nn
    contains_phrase = (
        "isn't in our safety documents" in an
        or "not in our safety documents" in an
        or (nn and nn[:50] in an)
    )
    short_refusal = len(an) <= len(nn) * 2 and contains_phrase
    replace_with_fallback = exact or short_refusal
    omit_sources = contains_phrase
    return (replace_with_fallback, omit_sources)


def analyze_query_complexity(query: str) -> dict:
    query_lower = query.lower()
    word_count = len(query.split())

    has_procedure = any(w in query_lower for w in ['steps', 'procedure', 'process', 'how to'])
    has_emergency = any(w in query_lower for w in ['emergency', 'accident', 'injury', 'occurs', 'if'])
    has_multiple = any(w in query_lower for w in ['and', 'also', 'plus', 'as well as'])
    is_yesno = query_lower.startswith(('can i', 'should i', 'is it', 'do i', 'may i', 'am i'))
    asks_for_all = any(w in query_lower for w in ['all', 'every', 'complete', 'full list'])
    asks_for_list = any(w in query_lower for w in ['ppe', 'equipment', 'tools', 'requirements', 'need', 'required'])

    score = 0
    reasoning = []
    if has_procedure:
        score += 3
        reasoning.append("procedure/steps requested")
    if has_emergency:
        score += 2
        reasoning.append("emergency scenario")
    if has_multiple:
        score += 2
        reasoning.append("multiple topics")
    if asks_for_all:
        score += 2
        reasoning.append("comprehensive answer requested")
    if asks_for_list:
        score += 2
        reasoning.append("list of items requested")
    if word_count > 12:
        score += 1
        reasoning.append("detailed question")
    if is_yesno and score == 0:
        score = -1
        reasoning.append("simple yes/no question")

    cfg = settings.SAFEGUARDAI
    complex_thresh = cfg['COMPLEXITY_COMPLEX_THRESHOLD']
    medium_thresh = cfg['COMPLEXITY_MEDIUM_THRESHOLD']
    if score >= complex_thresh:
        complexity = 'complex'
        target_length = tuple(cfg['COMPLEXITY_COMPLEX_TARGET'])
    elif score >= medium_thresh:
        complexity = 'medium'
        target_length = tuple(cfg['COMPLEXITY_MEDIUM_TARGET'])
    else:
        complexity = 'simple'
        target_length = tuple(cfg['COMPLEXITY_SIMPLE_TARGET'])

    return {
        'complexity': complexity,
        'target_length': target_length,
        'reasoning': ', '.join(reasoning) if reasoning else 'straightforward query'
    }


def _get_llm(temperature: float = 0.05) -> LLM:
    return LLM(
        model=settings.SAFEGUARDAI['OPENAI_MODEL'],
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )


def _build_researcher() -> Agent:
    return Agent(
        role='Senior Safety Specialist',
        goal=(
            'Produce a complete, accurate, and fully validated safety answer '
            'from the provided company documents. Check your own work for '
            'missing requirements, warnings, and emergency steps relevant to the topic.'
        ),
        backstory=(
            'You are a senior safety and compliance specialist with deep experience '
            'in workplace safety across multiple domains. You are meticulous — you never '
            'miss a critical requirement. You base your answers exclusively on the '
            'company documents provided. You self-review every answer before passing it on.'
        ),
        tools=[],
        llm=_get_llm(temperature=0.05),
        verbose=False,
        allow_delegation=False,
    )


def _build_formatter() -> Agent:
    return Agent(
        role='Safety Communications Specialist',
        goal=(
            'Format safety answers for WhatsApp using proper bold formatting, '
            'clean structure, and professional presentation within the target length.'
        ),
        backstory=(
            'You format safety information for field workers reading on mobile. '
            'You use WhatsApp formatting correctly. You write in clear, simple English. '
            'You adapt response length to match question complexity. '
            'You ALWAYS stay within the specified character limit. '
            'You follow formatting rules precisely every single time.'
        ),
        tools=[safety_image_tool],
        llm=_get_llm(temperature=0.05),
        verbose=False,
        allow_delegation=False,
    )


def _research_task(query: str, context: str, researcher: Agent) -> Task:
    not_in_docs_msg = _get_not_in_docs_message()
    return Task(
        description=f"""Answer this safety question using ONLY the documents below.

QUESTION: {query}

DOCUMENTS:
{context}

CRITICAL — WHEN YOU CANNOT ANSWER:
Reply with EXACTLY this sentence and nothing else (no *Source:*) when:
- The DOCUMENTS section is empty, or
- The excerpts are clearly unrelated to the question (e.g. meeting schedules, weather), or
- The excerpts do not contain information that answers this specific question (e.g. the question is about topic A but the excerpts only discuss topic B).
"{not_in_docs_msg}"

MANDATORY — WHEN YOU CAN ANSWER:
If the DOCUMENTS section contains safety-related text that answers or clearly relates to the question, you MUST answer using that text. Do NOT output the "not in documents" sentence. Use the excerpts under "From [document name]:". Even if the wording is not exact (e.g. question asks "PPE for arc flash" and the document says "arc-rated clothing and PPE required"), you MUST answer from the documents.
1. Use ONLY the text from the DOCUMENTS above. Do not add information from outside these excerpts.
2. Prefer information from the document that best matches the question topic.
3. Be thorough but concise. The system will show the user which documents were used.""",
        agent=researcher,
        expected_output=(
            'Complete safety answer from the documents, OR the single short "not in documents" sentence when the docs do not contain the answer.'
        ),
    )


def _format_task(query: str, research_task: Task, formatter: Agent, target_range: tuple) -> Task:
    min_chars, max_chars = target_range
    image_requested = _user_asked_for_image(query)
    trigger_phrases = _get_image_trigger_phrases()
    trigger_examples = ', '.join(f'"{p}"' for p in trigger_phrases[:8]) if trigger_phrases else 'show me, picture, image of, photo'
    image_block = (
        "*** MANDATORY: The user asked for an image/visual. "
        "You MUST call SafetyImageTool FIRST with a short description of what to show (e.g. 'safety equipment for the task' or 'procedure steps'). "
        "Include the full SAFEGUARD_IMAGE_URL:... line the tool returns, then add a brief caption. Do NOT reply with text only. ***\n\n"
        if image_requested
        else ""
    )
    return Task(
        description=f"""{image_block}Rewrite this safety answer for WhatsApp with proper formatting.

QUESTION: {query}

IMAGE REQUEST — CRITICAL:
If the user asked to see something visually (e.g. {trigger_examples}), you MUST use the SafetyImageTool FIRST. Call it with a clear description of what to show based on the question (e.g. "required safety equipment" or "procedure steps"). The tool returns a line like SAFEGUARD_IMAGE_URL:https://... — include that full line in your response so the system can send the image to WhatsApp. Then add a short caption (key points from the research). If the user did NOT ask for an image, do not use the tool; just format the research answer as text.

CRITICAL LENGTH REQUIREMENT:
Target: {min_chars}-{max_chars} characters
ABSOLUTE MAXIMUM: {max_chars + 50} characters
Count your characters as you write. Stop when you reach the limit.

WHATSAPP FORMATTING RULES:

1. BOLD TEXT - CRITICAL (WhatsApp only supports SINGLE asterisks):
   - Use ONLY single asterisks: *text* for bold. WhatsApp does NOT support ** double asterisks **.
   - NEVER use ** (double asterisks) - they will appear as raw symbols. Use * (single) only.
   - EVERY main header: *Key requirements* or similar (single asterisks each side)
   - EVERY subheader: *If Alarm Activates:* (single asterisks)
   - Check your output: no ** anywhere; only * for bold. One asterisk immediately before and after each bold phrase.

2. BULLET POINTS:
   - Use "- " (dash space) for all bullets

3. NUMBERED LISTS:
   - Use 1. 2. 3. for procedures

4. STRUCTURE:
   - Main bold header at top
   - One blank line between sections
   - Bold subheaders before content

5. PRIORITIZATION (if approaching character limit):
   - Critical warnings MUST be included
   - Required actions MUST be included
   - Specifications can be summarized
   - Examples can be cut

6. ENDING - CRITICAL:
   - If the research answer is the short "not in documents" message, output it UNCHANGED. Do not add structure or headers.
   - Do NOT add your own *Source:* or *Sources:* line — the system will append the document list automatically.
   - The response must NEVER be cut off mid-sentence. Every sentence must be complete.
   - If you approach the limit, shorten by removing the least critical detail, not by cutting a sentence.

WRITE YOUR RESPONSE. STAY WITHIN {max_chars} CHARACTERS.""",
        agent=formatter,
        expected_output=(
            f'Professional WhatsApp message with bold formatting, '
            f'{min_chars}-{max_chars} characters.'
        ),
        context=[research_task],
    )


def _simple_query_direct(query: str, context: str, target_range: tuple, not_in_docs_msg: str) -> str:
    """Fast path: answer simple safety queries with a single OpenAI call."""
    if not openai_client:
        logger.error("_simple_query_direct: OpenAI client not initialised")
        return not_in_docs_msg

    min_chars, max_chars = target_range
    model = settings.SAFEGUARDAI['OPENAI_MODEL']

    system_prompt = f"""You are SafeGuardAI, a workplace safety specialist answering questions for field workers on WhatsApp.

RULES:
1. Answer using ONLY the DOCUMENTS provided below. Do not add outside information.
2. If the documents do not contain the answer, reply with EXACTLY: "{not_in_docs_msg}"
3. Use WhatsApp formatting: *single asterisks* for bold (NEVER **double**), "- " for bullets, 1. 2. 3. for steps.
4. Target length: {min_chars}-{max_chars} characters. Do NOT exceed {max_chars} characters.
5. Do NOT add a *Source:* or *Sources:* line — the system appends sources automatically.
6. Every sentence must be complete. Never cut off mid-sentence."""

    user_prompt = f"""QUESTION: {query}

DOCUMENTS:
{context}"""

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.05,
            max_tokens=600,
        )
        return (response.choices[0].message.content or '').strip()
    except Exception as e:
        logger.error(f"_simple_query_direct: OpenAI call failed | error={e}")
        return not_in_docs_msg


def _extract_image_url(text: str) -> str | None:
    if not text:
        return None
    if SAFEGUARD_IMAGE_URL_PREFIX in text:
        idx = text.find(SAFEGUARD_IMAGE_URL_PREFIX)
        rest = text[idx + len(SAFEGUARD_IMAGE_URL_PREFIX):]
        match = re.match(r'(https://[^\s\n\)\]\>]+)', rest)
        if match:
            return match.group(1).rstrip('.,;')
    if 'oaidalleapiprodscus' in text:
        match = re.search(r'https://oaidalleapiprodscus\.blob\.core\.windows\.net/[^\s\n\)\]\>]+', text)
        if match:
            return match.group(0).rstrip('.,;')
    return None


def _best_distance(chunks: list) -> float | None:
    """Return the minimum cosine distance from a list of RAG result chunks."""
    best = None
    for chunk in chunks:
        d = chunk.get('distance')
        if d is not None:
            best = min(best, d) if best is not None else d
    return best


def process_safety_query(query: str, conversation_sources: list | None = None) -> dict:
    start_time = time.time()
    logger.info(f"Safety query | query='{query[:80]}'")

    complexity_info = analyze_query_complexity(query)
    logger.info(
        f"Query complexity | "
        f"level={complexity_info['complexity']} | "
        f"target={complexity_info['target_length']} | "
        f"reason={complexity_info['reasoning']}"
    )

    rag_start = time.time()
    rag = get_rag()
    n_results = settings.SAFEGUARDAI['RAG_NUM_RESULTS']
    rag_results = rag.search(query, n_results=n_results)
    rag_time = round(time.time() - rag_start, 2)

    not_in_docs_msg = _get_not_in_docs_message()

    if not rag_results:
        logger.warning(f"No RAG results | time={rag_time}s")
        return {
            'answer': not_in_docs_msg,
            'sources': [],
        }

    best_dist = _best_distance(rag_results)
    threshold = settings.SAFEGUARDAI['RAG_RELEVANCE_DISTANCE_THRESHOLD']
    if best_dist is not None and threshold is not None and best_dist > threshold:
        if conversation_sources:
            augmented_query = ' '.join(conversation_sources) + ' ' + query
            logger.info(
                f"RAG relevance gating | best_distance={best_dist:.3f} > {threshold} | "
                f"retrying with conversation context | sources={conversation_sources}"
            )
            rag_results_2 = rag.search(augmented_query, n_results=n_results)
            best_dist_2 = _best_distance(rag_results_2) if rag_results_2 else None
            if best_dist_2 is not None and best_dist_2 <= threshold:
                rag_results = rag_results_2
                best_dist = best_dist_2
                rag_time = round(time.time() - rag_start, 2)
                logger.info(
                    f"RAG retry with conversation context passed | "
                    f"best_distance={best_dist_2:.3f} | sources={conversation_sources}"
                )
            else:
                logger.info(
                    f"RAG retry still above threshold | best_distance={best_dist_2}"
                )
                return {'answer': not_in_docs_msg, 'sources': []}
        else:
            logger.info(
                f"RAG relevance gating | best_distance={best_dist:.3f} > {threshold} | "
                f"returning not-in-documents (no relevant chunks)"
            )
            return {'answer': not_in_docs_msg, 'sources': []}

    context = '\n\n'.join([
        f"From {chunk['source']}:\n{chunk['text']}"
        for chunk in rag_results
    ])
    sources = list(set(chunk['source'] for chunk in rag_results))
    logger.info(
        f"RAG complete | chunks={len(rag_results)} | "
        f"sources={sources} | time={rag_time}s"
    )

    if _query_expects_topic_not_in_sources(query, sources):
        logger.info(
            f"Topic gating | query asks for topic not in retrieved sources | "
            f"sources={sources} | returning not-in-documents"
        )
        return {
            'answer': not_in_docs_msg,
            'sources': [],
        }

    agents_start = time.time()

    # Simple queries: single OpenAI call (~3–5s). Medium/complex: full CrewAI pipeline (~10–15s).
    if complexity_info['complexity'] == 'simple' and not _user_asked_for_image(query):
        logger.info("Simple query — using direct OpenAI fast path")
        answer = _simple_query_direct(query, context, complexity_info['target_length'], not_in_docs_msg)
        agents_time = round(time.time() - agents_start, 2)
        logger.info(f"Direct fast path complete | time={agents_time}s")
    else:
        logger.info(f"CrewAI pipeline started | complexity={complexity_info['complexity']}")
        researcher = _build_researcher()
        formatter = _build_formatter()
        task_research = _research_task(query, context, researcher)
        task_format = _format_task(
            query,
            task_research,
            formatter,
            complexity_info['target_length']
        )
        crew = Crew(
            agents=[researcher, formatter],
            tasks=[task_research, task_format],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        answer = str(result).strip()
        agents_time = round(time.time() - agents_start, 2)
        logger.info(f"CrewAI pipeline complete | time={agents_time}s")

    max_len = settings.SAFEGUARDAI['MAX_WHATSAPP_MESSAGE_LENGTH']

    while '**' in answer:
        answer = answer.replace('**', '*')
    if answer.count('*') % 2 != 0:
        logger.warning("Odd number of asterisks after ** normalisation — bold may be unbalanced")
    logger.debug("WhatsApp bold normalisation applied (** -> *)")

    replace_with_fallback, omit_sources = _classify_not_in_docs_reply(answer, not_in_docs_msg)
    if replace_with_fallback:
        answer = not_in_docs_msg
        sources = []

    answer = re.sub(r'\n?\s*\*?Sources?:\*?\s*[^\n]*', '', answer).strip()

    image_url = _extract_image_url(answer)
    if image_url:
        logger.info(f"DALL·E image URL extracted | length={len(image_url)}")

    if _user_asked_for_image(query) and not image_url:
        description = _description_for_image(query)
        logger.info(f"Image requested but formatter did not call tool; generating image | description='{description[:60]}'")
        try:
            tool_out = safety_image_tool.run(description=description)
            image_url = _extract_image_url(tool_out or '')
            if image_url:
                logger.info(f"DALL·E image generated (fallback) | length={len(image_url)}")
        except Exception as e:
            logger.warning(f"Fallback image generation failed | error={e}")

    if image_url:
        answer = re.sub(r'\n?' + re.escape(SAFEGUARD_IMAGE_URL_PREFIX) + r'[^\n]*', '', answer)
        answer = re.sub(r'\n?View here:\s*https?://[^\n]+', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\n?Note:\s*This link expires[^\n]*', '', answer)
        answer = re.sub(r'https?://[^\s\n\)\]\>\"]+', '', answer, flags=re.IGNORECASE)
        answer = re.sub(r'(?m)^\s*https?://[^\s\n]+\s*\r?\n?', '', answer)
        answer = re.sub(r'!\[[^\]]*\]\s*\(\s*\)', '', answer)
        answer = re.sub(r'\n{3,}', '\n\n', answer)
        answer = re.sub(r'  +', ' ', answer)
        answer = answer.strip()

    if len(answer) > max_len:
        logger.warning(
            f"Response exceeded hard limit | "
            f"length={len(answer)} | max={max_len} | trimming at sentence boundary"
        )
        trim_at = max_len - 1
        for sep in ('. ', '! ', '? ', '\n'):
            idx = answer.rfind(sep, 0, trim_at + 1)
            if idx != -1:
                answer = answer[: idx + len(sep)].rstrip()
                break
        else:
            last_space = answer.rfind(' ', 0, trim_at + 1)
            answer = answer[: last_space + 1].rstrip() if last_space > 0 else answer[:trim_at].rstrip()
        if answer and not answer.endswith(('.', '!', '?')):
            answer += '.'

    if sources and not omit_sources:
        answer = answer + "\n\n*Sources:* " + ", ".join(sources)

    total_time = round(time.time() - start_time, 2)
    logger.info(
        f"Query complete | "
        f"total={total_time}s | rag={rag_time}s | agents={agents_time}s | "
        f"length={len(answer)} chars | "
        f"complexity={complexity_info['complexity']}"
    )

    return {
        'answer': answer,
        'sources': sources,
        'image_url': image_url,
    }
