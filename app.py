import os
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import mysql.connector
import hashlib

# Load environment variables
load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

# MySQL config
mysql_config = {
    'host': os.getenv("MYSQL_HOST"),
    'user': os.getenv("MYSQL_USER"),
    'password': os.getenv("MYSQL_PASSWORD"),
    'database': os.getenv("MYSQL_DATABASE")
}

# Initialize LLM
llm = ChatOpenAI(openai_api_key=api_key, model_name="gpt-4o-mini", temperature=0)

# Streamlit config
st.set_page_config(page_title="ScriptBot", layout="wide")

# Initialize session states
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "code_outputs" not in st.session_state:
    st.session_state.code_outputs = []

# --- DB Setup ---
def init_db():
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            question TEXT,
            answer TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                       (username, hash_password(password)))
        conn.commit()
        return True
    except mysql.connector.errors.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username=%s AND password_hash=%s",
                   (username, hash_password(password)))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

def insert_history(user_id, question, answer):
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, question, answer) VALUES (%s, %s, %s)",
                   (user_id, question, answer))
    conn.commit()
    conn.close()

def get_all_history(user_id):
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, answer FROM history WHERE user_id = %s ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_history_entry(entry_id, user_id):
    conn = mysql.connector.connect(**mysql_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = %s AND user_id = %s", (entry_id, user_id))
    conn.commit()
    conn.close()

init_db()

# --- Authentication Section with tabs and styled welcome message ---
def login_register_section():
    st.markdown("""
        <style>
        .title-icon {
            font-size: 1.5rem;
            vertical-align: middle;
            margin-right: 0.3rem;
        }
        .welcome-container {
            max-width: 500px;
            margin: 0;
            padding: 1rem 0 1rem 1rem;
            background-color: #1e1e1e;
            border-radius: 8px;
            color: white;
            text-align: left;
            font-size: 1.3rem;
            font-weight: 60;
            display: flex;
            align-items: center;
        }
        .stTextInput > div > input {
            background-color: #2e2e2e;
            color: white;
            border: none;
            border-radius: 5px;
            height: 35px;
            padding-left: 10px;
        }
        .stButton > button {
            background-color: #007bff;
            color: white;
            border-radius: 5px;
            height: 40px;
            width: 100px;
            border: none;
            cursor: pointer;
        }
        .stButton > button:hover {
            background-color: #0056b3;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="welcome-container">'
        '<span class="title-icon">🤖</span>'
        'Welcome to ScriptBot'
        '</div>',
        unsafe_allow_html=True
    )

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("🔑 Login to your account")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login")
            if login_btn:
                user_id = login_user(username, password)
                if user_id:
                    st.session_state.user_id = user_id
                    st.session_state.username = username
                    st.success(f"✅ Welcome back, {username}!")
                    st.rerun()

                else:
                    st.error("❌ Invalid credentials.")

    with tab2:
        st.subheader("📝 Register a new account")
        with st.form("register_form"):
            new_username = st.text_input("New Username", key="reg_username")
            new_password = st.text_input("New Password", type="password", key="reg_password")
            register_btn = st.form_submit_button("Register")
            if register_btn:
                if register_user(new_username, new_password):
                    st.success("🎉 Registration successful! Please log in.")
                else:
                    st.error("⚠ Username already exists.")

# If user not logged in, show login/register UI
if not st.session_state.user_id:
    login_register_section()
    st.stop()

# Top header
st.markdown("<h1 style='text-align: center;'>ScriptBot 🤖</h1>", unsafe_allow_html=True)


# Prompt templates
base_prompt_template = PromptTemplate(
    input_variables=["question"],
    template="""You are a coding assistant. The user needs help writing code.
Here is the question: {question}
Please provide a clean, complete code solution with necessary imports and a short explanation."""
)

def generate_code(question):
    prompt = base_prompt_template.format(question=question)
    return llm.predict(prompt)

# Sidebar
st.sidebar.title(f"🕓 History ({st.session_state.username})")
history = get_all_history(st.session_state.user_id)
if history:
    for entry_id, question, answer in history:
        if st.sidebar.button(f"📄 {question[:30]}...", key=f"load_{entry_id}"):
            st.session_state.code_outputs.insert(0, (question, answer))
            st.rerun()

        if st.sidebar.button("🗑️ Delete", key=f"delete_{entry_id}"):
            delete_history_entry(entry_id, st.session_state.user_id)
            st.session_state.code_outputs = get_all_history(st.session_state.user_id)
            st.rerun()

else:
    st.sidebar.info("No history yet.")

if st.sidebar.button("🚪 Logout"):
    for key in ["user_id", "username", "code_outputs"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


# Display previous results
st.markdown('<div style="padding-bottom: 200px;">', unsafe_allow_html=True)
for question, answer in st.session_state.code_outputs:
    st.markdown(f"### ❓ Question: {question}")
    st.code(answer)
st.markdown('</div>', unsafe_allow_html=True)

# --- Fixed input at bottom ---
st.markdown("""
    <style>
    .fixed-input {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 70%;
        background-color: white;
        padding: 1rem;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
        z-index: 999;
    }
    .fixed-input textarea {
        width: 100% !important;
    }
    </style>
    <div class='fixed-input'>
""", unsafe_allow_html=True)

with st.form("input_form", clear_on_submit=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        question = st.text_area("Ask a coding question", label_visibility="collapsed", height=80)
    with col2:
        submit = st.form_submit_button("➤")

    if submit and question:
        try:
            answer = generate_code(question)
            insert_history(st.session_state.user_id, question, answer)
            st.session_state.code_outputs.append((question, answer))
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

st.markdown("</div>", unsafe_allow_html=True)
