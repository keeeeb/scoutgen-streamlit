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
fishing_company = st.text_input("🏢 釣り求人に含まれる企業名（例：キャディ）")
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
def build_prompt(profile, rag_context):
    return f"""
以下の候補者プロフィール、釣り求人情報、社内のテンプレート文、企業ナレッジ（RAG）をもとに、候補者の経歴・希望とマッチする件名と本文を生成してください。

【候補者プロフィール】
{profile}

【釣り求人情報（3社）】
★ユーザベース［経営戦略を“現場から動かす”情報プラットフォームSaaSを展開］
∟⽇本を代表する大企業の“経営戦略”に入り込み、複数プロダクトを駆使して課題を解決するセールス兼BizDev［年収756〜1350万円］

★エクサウィザーズ［生成AI導入ソリューション市場シェアNo.1｜AI×SaaSの新規事業を牽引］
∟"誰も経験したことのない営業を。"生成AI×SaaSの国内No.1を目指し、ARR11億円達成のプロダクト拡販・事業開発を担うセールス［年収〜960万円］

★キャディ［“日本発グローバル×製造業DX”を本気で実現するSaaSスタートアップ］
∟製造業のGoogleをつくる。巨大データを活かしたBizDevセールス［年収770〜1600万円＋SO］

【テンプレート文】
件名：
【戦略視点で動くセールスへ】日本を代表する大企業の経営戦略に入り込むコンサルタント#年収770〜1350万円

本文：
━━━━━━━━━━━━━━━━━━━━━
あなたの次のキャリアステップを、私たちと共に。
━━━━━━━━━━━━━━━━━━━━━

こんにちは、SIESTA代表の久保です。

あなたの実績と経歴に拝読し、あなたの市場価値を弊社がコミットすればさらに高められると考えオファーメールをお送りさせていただきました。

私たちと共に、【上位1％】に入るキャリアの高みを目指しませんか？

━━━━━━━━━━━━━━━━━━━━━
━ 上位1%転職成功のための弊社独自の秘訣 ━
━━━━━━━━━━━━━━━━━━━━━
【1】弊社の完全支援で貴方の評価をアップさせる職務経歴書作成と面接対策（過去合格者の面接回答例等）。
【2】それにより「複数の内定を最高評価で獲得」して、選択肢を増やしながら条件交渉を有利に進める。
【3】元リクルートMVP営業が見出した貴方に有利な条件を獲得するための…

【企業ナレッジ（RAG抽出）】
{rag_context}

【出力形式】
件名：◯◯◯◯（50文字以内）
本文：
◯◯◯◯（1800文字前後）
"""

# --- メイン処理 ---
if generate_button and openai_api_key and candidate_profile:
    rag_context = ""
    if fishing_company:
        st.info("🔍 Google Driveから企業ナレッジを取得中...")
        rag_context = find_doc_content_by_keyword(fishing_company)

    if rag_context:
        with st.expander("🔍 取得した企業ナレッジ（RAG）を確認"):
            st.markdown(rag_context)

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
    prompt = build_prompt(candidate_profile, rag_context)
    messages = [SystemMessage(content="あなたはハイクラス人材にスカウト文を作成するプロです。"),
                HumanMessage(content=prompt)]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を入力してください")
