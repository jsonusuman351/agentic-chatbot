import json
import os
import time
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

UI_VERSION = 'v2.0'
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:8000').rstrip('/')

TOOL_ICONS = {
    'calculator': '🧮',
    'current_time': '🕒',
    'get_current_time': '🕒',
    'time': '🕒',
    'weather': '⛅',
    'get_weather': '⛅',
}

EXAMPLE_PROMPTS = [
    ('🧮 Calculator', 'What is (125 * 48) / 6 + 77?'),
    ('🕒 Current time', 'What is the current time in Tokyo?'),
    ('⛅ Weather', 'What is the weather in Indore right now?'),
    ('🔗 Multi-tool', 'What is the weather in Delhi and what time is it there?'),
]

st.set_page_config(
    page_title='Agentic Chatbot',
    page_icon='🤖',
    layout='centered',
    initial_sidebar_state='expanded',
)

# ---------- Styling ----------
st.markdown(
    """
    <style>
        .block-container { padding-top: 2rem; }
        .tool-badge {
            display: inline-block;
            padding: 2px 10px;
            margin: 2px 4px 2px 0;
            border-radius: 999px;
            font-size: 0.78rem;
            background: rgba(120, 120, 255, 0.15);
            border: 1px solid rgba(120, 120, 255, 0.35);
        }
        .meta { font-size: 0.75rem; opacity: 0.6; margin-top: 4px; }
        .status-dot { font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Helpers ----------
def init_state():
    defaults = {
        'messages': [],
        'pending_prompt': None,
        'failed_prompt': None,
        'backend_status': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def check_backend():
    """Ping backend. Tries /health first, then falls back to /docs."""
    for path in ('/health', '/docs'):
        try:
            r = requests.get(f'{BACKEND_URL}{path}', timeout=5)
            if r.status_code < 500:
                return True, f'Online ({path} -> {r.status_code})'
        except requests.RequestException:
            continue
    return False, 'Unreachable'


def call_backend(prompt, history, timeout):
    start = time.perf_counter()
    response = requests.post(
        f'{BACKEND_URL}/chat',
        json={'message': prompt, 'history': history},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    latency = time.perf_counter() - start
    return data, latency


def clean_history(messages):
    """Only send role/content to the backend (keeps payload identical to v1)."""
    return [{'role': m['role'], 'content': m['content']} for m in messages]


def stream_text(text, delay=0.012):
    """Typing effect for st.write_stream."""
    for word in text.split(' '):
        yield word + ' '
        time.sleep(delay)


def render_tool_badges(tool_calls):
    if not tool_calls:
        return
    badges = ''.join(
        f'<span class="tool-badge">{TOOL_ICONS.get(t, "🔧")} {t}</span>'
        for t in tool_calls
    )
    st.markdown(badges, unsafe_allow_html=True)


def render_message(message, show_tools=True, show_meta=True):
    with st.chat_message(message['role']):
        st.markdown(message['content'])
        if message['role'] == 'assistant':
            if show_tools:
                render_tool_badges(message.get('tool_calls', []))
            if show_meta and message.get('latency') is not None:
                st.markdown(
                    f'<div class="meta">⏱ {message["latency"]:.2f}s · {message.get("ts", "")}</div>',
                    unsafe_allow_html=True,
                )


def export_markdown(messages):
    lines = [f'# Chat export - {datetime.now():%Y-%m-%d %H:%M}\n']
    for m in messages:
        who = 'You' if m['role'] == 'user' else 'Assistant'
        lines.append(f'**{who}:** {m["content"]}\n')
        if m.get('tool_calls'):
            lines.append(f'_Tools used: {", ".join(m["tool_calls"])}_\n')
    return '\n'.join(lines)


init_state()

# ---------- Sidebar ----------
with st.sidebar:
    st.header('⚙️ Control Panel')

    st.subheader('Backend')
    st.code(BACKEND_URL)
    if st.button('🔌 Check connection', use_container_width=True):
        with st.spinner('Pinging backend...'):
            st.session_state.backend_status = check_backend()
    status = st.session_state.backend_status
    if status is not None:
        ok, msg = status
        (st.success if ok else st.error)(msg)

    st.divider()
    st.subheader('Settings')
    show_tools = st.toggle('Show tools used', value=True)
    show_meta = st.toggle('Show response time', value=True)
    typing_effect = st.toggle('Typing effect', value=True)
    timeout = st.slider('Request timeout (sec)', 10, 300, 120, step=10)

    st.divider()
    st.subheader('Available tools')
    st.markdown('🧮 Calculator  \n🕒 Current time  \n⛅ Weather')

    st.divider()
    st.subheader('Session')
    msgs = st.session_state.messages
    assistant_msgs = [m for m in msgs if m['role'] == 'assistant']
    tools_total = sum(len(m.get('tool_calls', [])) for m in assistant_msgs)
    latencies = [m['latency'] for m in assistant_msgs if m.get('latency') is not None]
    c1, c2 = st.columns(2)
    c1.metric('Messages', len(msgs))
    c2.metric('Tool calls', tools_total)
    if latencies:
        st.metric('Avg response', f'{sum(latencies) / len(latencies):.2f}s')

    st.divider()
    if msgs:
        st.download_button(
            '⬇️ Export (Markdown)',
            data=export_markdown(msgs),
            file_name='chat_export.md',
            mime='text/markdown',
            use_container_width=True,
        )
        st.download_button(
            '⬇️ Export (JSON)',
            data=json.dumps(msgs, indent=2),
            file_name='chat_export.json',
            mime='application/json',
            use_container_width=True,
        )
    if st.button('🗑️ Clear chat', use_container_width=True):
        st.session_state.messages = []
        st.session_state.failed_prompt = None
        st.rerun()

    st.caption(f'UI {UI_VERSION}')

# ---------- Header ----------
st.title('🤖 Agentic Chatbot')
st.caption('Streamlit UI → FastAPI → LangGraph Agent → Tools → Response')

# ---------- Empty state: example prompts ----------
if not st.session_state.messages:
    st.info('👋 Ask me anything, or try one of these:')
    cols = st.columns(2)
    for i, (label, text) in enumerate(EXAMPLE_PROMPTS):
        if cols[i % 2].button(label, key=f'example_{i}', use_container_width=True, help=text):
            st.session_state.pending_prompt = text
            st.rerun()

# ---------- Render history ----------
for message in st.session_state.messages:
    render_message(message, show_tools, show_meta)

# ---------- Action row under last reply ----------
messages = st.session_state.messages
if messages and messages[-1]['role'] == 'assistant':
    col_a, col_b, _ = st.columns([1, 1, 4])
    if col_a.button('🔄 Regenerate', key='regen'):
        messages.pop()  # assistant reply
        last_user = messages.pop()  # user prompt
        st.session_state.pending_prompt = last_user['content']
        st.rerun()
    if col_b.button('↩️ Undo', key='undo'):
        messages.pop()
        messages.pop()
        st.rerun()

# ---------- Retry after failure ----------
if st.session_state.failed_prompt:
    st.warning('The last request failed.')
    if st.button('🔁 Retry last message'):
        st.session_state.pending_prompt = st.session_state.failed_prompt
        st.session_state.failed_prompt = None
        st.rerun()

# ---------- Input ----------
typed_prompt = st.chat_input('Ask something...')
prompt = st.session_state.pending_prompt or typed_prompt
st.session_state.pending_prompt = None

if prompt:
    st.session_state.failed_prompt = None
    history = clean_history(st.session_state.messages)

    user_msg = {'role': 'user', 'content': prompt}
    st.session_state.messages.append(user_msg)
    render_message(user_msg)

    with st.chat_message('assistant'):
        try:
            with st.spinner('Agent is thinking and calling tools...'):
                data, latency = call_backend(prompt, history, timeout)

            answer = data['answer']
            tool_calls = data.get('tool_calls', [])

            if typing_effect:
                st.write_stream(stream_text(answer))
            else:
                st.markdown(answer)

            if show_tools:
                render_tool_badges(tool_calls)
            ts = f'{datetime.now():%H:%M:%S}'
            if show_meta:
                st.markdown(
                    f'<div class="meta">⏱ {latency:.2f}s · {ts}</div>',
                    unsafe_allow_html=True,
                )

            st.session_state.messages.append(
                {
                    'role': 'assistant',
                    'content': answer,
                    'tool_calls': tool_calls,
                    'latency': latency,
                    'ts': ts,
                }
            )
            st.rerun()

        except requests.Timeout:
            st.session_state.messages.pop()  # drop orphan user message
            st.session_state.failed_prompt = prompt
            st.error(f'Request timed out after {timeout}s. Try again or raise the timeout in the sidebar.')
        except requests.RequestException as exc:
            st.session_state.messages.pop()
            st.session_state.failed_prompt = prompt
            st.error(f'Backend connection failed: {exc}')
        except Exception as exc:
            st.session_state.messages.pop()
            st.session_state.failed_prompt = prompt
            st.error(f'Unexpected error: {exc}')