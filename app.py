import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import re
import os

# --- ページ設定 ---
st.set_page_config(page_title="RAGスカウト文ジェネレーター v3.0", layout="centered")
st.title("🧠 RAG × スカウトテンプレ自動生成 v3.0")

# --- OpenAI APIキー ---
openai_api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

# --- 入力欄 ---
candidate_profile = st.text_area("📄 候補者プロフィールを貼ってください")
fishing_job_1 = st.text_input("🎯 釣り求人①（社名_求人タイトル）")
fishing_job_2 = st.text_input("🎯 釣り求人②（社名_求人タイトル）")
fishing_job_3 = st.text_input("🎯 釣り求人③（社名_求人タイトル）")
contact_person = st.text_input("🧑‍💼 スカウト送信者名（署名に表示）")
generate_button = st.button("🚀 スカウト文を生成")

# --- Google Driveからドキュメント取得関数 ---
def find_doc_content_by_keyword(keyword: str):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    raw_json = st.secrets["SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(raw_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    query = f"mimeType='application/vnd.google-apps.document' and name contains '{keyword.split('_')[0]}'"
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
def build_prompt(profile, rag_summary, jobs, sender):
    jobs_bullet = "\n".join([f"★{j}\n∟▶︎（この求人の魅力・強み・ポジション情報をWeb検索済みと仮定してキャッチーに要約）" for j in jobs if j])

    return f"""
以下の構造・ルールに沿って、件名と本文を生成してください。

【スカウト文構造】
1. キャッチ：上位1%、年収UP、成長企業などで冒頭を印象づける（1文）
2. 自己紹介：{sender}の紹介は1文以内（端的に）
3. スカウト理由：候補者のプロフィール内容に共感・評価する文（2〜3文）
4. SIESTAの支援内容・実績：上位1%転職、完全支援、年収UP実績などを強く打ち出す
5. 釣り求人3件：キャッチーに訴求（社名＋魅力＋ポジション＋年収など）
6. 締め：カジュアル面談や情報交換など前向きな締め（押しすぎず）
7. 署名：SIESTA代表 {sender} として文末に固定

【候補者プロフィール】
{profile}

【釣り求人（Web検索済と仮定）】
{jobs_bullet}

【RAGで取得した企業情報】
{rag_summary}

【出力形式】
件名：◯◯◯◯
本文：

━━━━━━━━━━━━━━━━━━━━━
あなたの次のキャリアステップを、私たちと共に。
━━━━━━━━━━━━━━━━━━━━━

◯◯◯◯（1800文字前後）
━━━━━━━━━━━━━━━━━━━━━
{sender}｜SIESTA代表
━━━━━━━━━━━━━━━━━━━━━
"""

# --- メイン処理 ---
if generate_button and openai_api_key and candidate_profile:
    rag_summary = ""
    for keyword in [fishing_job_1, fishing_job_2, fishing_job_3]:
        if keyword:
            st.info(f"🔍 {keyword} の情報を取得中...")
            content = find_doc_content_by_keyword(keyword)
            if content:
                rag_summary += f"【{keyword}】\n{content}\n\n"

    if rag_summary:
        with st.expander("🔍 取得した企業ナレッジ（RAG）"):
            st.markdown(rag_summary)

    jobs = [fishing_job_1, fishing_job_2, fishing_job_3]

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
    prompt = build_prompt(candidate_profile, rag_summary, jobs, contact_person)
    messages = [
        SystemMessage(content="あなたはプロのスカウト文作成エージェントです。構成、トーン、訴求軸を厳密に守ってください。"),
        HumanMessage(content=prompt)
    ]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を環境変数またはSecretsに設定してください")
