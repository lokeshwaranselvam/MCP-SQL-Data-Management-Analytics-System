import streamlit as st
import mysql.connector
import pandas as pd
import requests
import json

# ========== CONFIGURATION ==========
GEMINI_API_KEY = "AIzaSyCs2zIRRQRQpw9w4JGYWlaK8kiNS6rNXeo"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
MYSQL_PASSWORD = "12345"
MYSQL_DATABASE = "students"
LOGIN_FILE = "admin_login.json"
# ===================================

# Load admin credentials
def load_admin_credentials():
    try:
        with open(LOGIN_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Authenticate admin
def authenticate(username, password):
    credentials = load_admin_credentials()
    return credentials.get(username) == password

# Get SQL from Gemini
def get_sql_from_gemini(question):
    prompt_template = """
You are an expert SQL assistant.
Convert the following natural language question into a MySQL SQL query using these tables:

STUDENT(NAME, CLASS, SECTION, MARKS)
COURSE(CLASS, COURSE_NAME, INSTRUCTOR)
ATTENDANCE(NAME, DATE, STATUS)

Only return the SQL query. No explanation.

Question: {question}
"""
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    prompt = prompt_template.format(question=question)
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        content = response.json()
        raw_sql = content['candidates'][0]['content']['parts'][0]['text'].strip()
        cleaned_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
        return cleaned_sql
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return None

# Execute MySQL Query
def run_query(sql):
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        cursor.execute(sql)

        if sql.lower().strip().startswith("select"):
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(rows, columns=columns)
        else:
            conn.commit()
            return "non_select"
    except Exception as e:
        st.error(f"MySQL Error: {e}")
        return None
    finally:
        if conn.is_connected():
            conn.close()

# ========== Streamlit UI ========== #
st.set_page_config(page_title="EduSQL: Student Database App", layout="wide")
st.markdown("<h1 style='text-align: center;'>EduSQL: Student Database App</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center;'>Query and manage your student database with ease</h4>", unsafe_allow_html=True)
st.write("## To Handle SQL Data")

question = st.text_input("Input:", placeholder="e.g. Show who was absent on 2024-03-15")
if st.button("Ask the question"):
    sql = get_sql_from_gemini(question)
    if sql:
        st.subheader("Generated SQL:")
        st.code(sql, language='sql')
        result = run_query(sql)

        if isinstance(result, pd.DataFrame):
            st.success("✅ Query executed successfully!")
            st.dataframe(result)
            csv = result.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download CSV", csv, "results.csv", "text/csv")
        elif result == "non_select":
            st.success("✅ SQL command executed successfully.")
        else:
            st.warning("⚠️ No data returned.")
    else:
        st.error("❌ Failed to generate SQL.")

# ========== Sidebar ========== #
st.sidebar.markdown("## Admin Panel")

enable_upload = st.sidebar.checkbox("Enable Admin Upload")
username = st.sidebar.text_input("👤 Username")
password = st.sidebar.text_input("🔒 Password", type="password")

if authenticate(username, password):
    st.sidebar.success("✅ Admin authenticated")
    uploaded_file = st.sidebar.file_uploader("📁 Upload CSV File", type=["csv"])
    table_name = st.sidebar.text_input("📌 Table Name to Insert Into")

    if uploaded_file and table_name:
        try:
            df = pd.read_csv(uploaded_file)

            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            result = cursor.fetchone()

            if not result:
                # Create table dynamically
                col_defs = []
                for col in df.columns:
                    dtype = "VARCHAR(255)"
                    if pd.api.types.is_integer_dtype(df[col]):
                        dtype = "INT"
                    elif pd.api.types.is_float_dtype(df[col]):
                        dtype = "FLOAT"
                    elif pd.api.types.is_datetime64_any_dtype(df[col]):
                        dtype = "DATE"
                    col_defs.append(f"`{col}` {dtype}")
                create_sql = f"CREATE TABLE `{table_name}` ({', '.join(col_defs)})"
                cursor.execute(create_sql)
                st.sidebar.success(f"🆕 Table `{table_name}` created.")

            # Insert data
            for _, row in df.iterrows():
                placeholders = ", ".join(["%s"] * len(row))
                insert_sql = f"INSERT INTO `{table_name}` VALUES ({placeholders})"
                cursor.execute(insert_sql, tuple(row))

            conn.commit()
            st.sidebar.success(f"✅ Uploaded to `{table_name}` successfully.")
            st.dataframe(df)

        except Exception as e:
            st.sidebar.error(f"❌ Upload error: {e}")

        finally:
            if conn.is_connected():
                conn.close()

else:
    st.sidebar.warning("🔐 Admin not authenticated")

st.sidebar.markdown("## 🔍 Test Queries")
st.sidebar.selectbox("Choose a sample query", [
    "Show who was absent on 2024-03-15",
    "Show all rows in table student_sport_list",
    "Get average marks for section B"
])