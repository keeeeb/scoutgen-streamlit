import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import re

# --- ページ設定 ---
st.set_page_config(page_title="RAGスカウト文ジェネレーター", layout="centered")
st.title("🧠 RAG × スカウトテンプレ自動生成")

# --- OpenAI APIキー入力 ---
openai_api_key = st.text_input("🔑 OpenAI API Key", type="password")

# --- 入力欄 ---
candidate_profile = st.text_area("📄 候補者プロフィールを貼ってください")
fishing_company_1 = st.text_input("🏢 釣り求人①に含まれる企業名")
fishing_company_2 = st.text_input("🏢 釣り求人②に含まれる企業名")
fishing_company_3 = st.text_input("🏢 釣り求人③に含まれる企業名")
generate_button = st.button("🚀 スカウト文を生成")

# --- Google Driveからドキュメント取得関数 ---
def find_doc_content_by_keyword(keyword: str):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    raw_json = st.secrets["SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(raw_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    query = f"mimeType='application/vnd.google-apps.document' and name contains '{keyword}'"
    results = drive_service.files().list(q=query, fields="files(id, name)", pageSize=5).execute()
    files = results.get('files', [])

    if not files:
        return ""

    file_id = files[0]['id']
    doc_service = build('docs', 'v1', credentials=creds)
    doc = doc_service.documents().get(documentId=file_id).execute()

    content = ""
    for element in doc.get("body").get("content"):
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                text_run = elem.get("textRun")
                if text_run:
                    content += text_run.get("content")

    cleaned = re.sub(r'\n{2,}', '\n\n', content.strip())
    return cleaned

# --- スカウト文生成プロンプト ---
def build_prompt(profile, rag_summary):
    return f"""
以下の候補者プロフィール、釣り求人情報、テンプレート文、企業ナレッジ（RAG）をもとに、
必ず件名と本文を生成してください。

【候補者プロフィール】
{profile}

【テンプレート件名】
【戦略視点で動くセールスへ】日本を代表する大企業の経営戦略に入り込むコンサルタント#年収770〜1350万円

【テンプレート本文冒頭】
━━━━━━━━━━━━━━━━━━━━━
あなたの次のキャリアステップを、私たちと共に。
━━━━━━━━━━━━━━━━━━━━━

こんにちは、SIESTA代表の久保です。

あなたの実績と経歴に拝読し、あなたの市場価値を弊社がコミットすればさらに高められると考えオファーメールをお送りさせていただきました。

私たちと共に、【上位1％】に入るキャリアの高みを目指しませんか？

【企業ナレッジ（RAG）】
{rag_summary}

必ず上記内容を活用し、自然に馴染ませて件名（50文字以内）と本文（1800文字前後）を日本語で生成してください。
【出力形式】
件名：◯◯◯◯
本文：
◯◯◯◯
"""

# --- メイン処理 ---
if generate_button and openai_api_key and candidate_profile:
    # RAG取得
    summary_list = []
    for keyword in [fishing_company_1, fishing_company_2, fishing_company_3]:
        if keyword:
            st.info(f"🔍 {keyword} の情報を取得中...")
            content = find_doc_content_by_keyword(keyword)
            if content:
                summary_list.append(f"【{keyword}】\n{content.strip()}\n")
    rag_summary = "\n\n".join(summary_list)

    if rag_summary:
        with st.expander("🔍 取得した企業ナレッジ（RAG）"):
            st.markdown(rag_summary)

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
    prompt = build_prompt(candidate_profile, rag_summary)
    messages = [
        SystemMessage(content="あなたはハイクラス人材にスカウト文を作成するプロです。"),
        HumanMessage(content=prompt)
    ]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を入力してください")
