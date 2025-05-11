import io
import re
import os
import requests
import streamlit as st
import openai
from newsapi import NewsApiClient
from datetime import datetime, timedelta, timezone
from fpdf import FPDF

st.set_page_config(layout="wide")

openai.api_key = st.secrets["api_key_openai"]
api_key_newsapi = st.secrets["api_key_newsapi"]
api_key_naver_client_id = st.secrets["api_key_naver_client_id"]
api_key_naver_client_secret = st.secrets["api_key_naver_client_secret"]

st.title(":earth_asia: TECH INTELLIGENCE")
st.markdown("""
- 국가전략기술 관련 글로벌 뉴스 수집 및 분석 도구 (Proof of Concept Version)
- Developed by **KISTEP 전략기술정책센터**
- 국내뉴스는 관련도 순 최대 100개의 뉴스가 검색됩니다.
- 정기적(매일) 수신을 원할 경우 stc@kistep.re.kr로 문의주시기 바랍니다.
""")

st.subheader("Search Parameters")
cols_query = st.columns(4)
query_kor = cols_query[0].text_input("검색키워드(국내)", "AI", help="네이버 뉴스 검색 키워드")
query_glo = cols_query[1].text_input("검색키워드(국외)", "AI", help="글로벌 뉴스 검색 키워드")

time_span = cols_query[2].text_input("검색기간(일)", 1) # Set Time Range
today = datetime.now()
start_date = today - timedelta(days=1)
start_date = start_date.strftime("%Y-%m-%d")
end_date = today.strftime("%Y-%m-%d")

model_options = ["gpt-4.1-mini", "gpt-4o", "gpt-4.1"] # OpenAI Model Selection
selected_model = cols_query[3].selectbox("AI 모델을 선택하세요", model_options, help="뉴스 요약 모델")


# Set Some option
cols = st.columns(3)
use_lang = cols[0].checkbox("언어(국외)")
title_only = cols[1].checkbox("제목만(국외)")
major_only = cols[2].checkbox("주요 언론사만(공사중)")

if use_lang:
    # ISO-639-1 코드 예시 목록
    lang_options = ["en","ar","de","en","es","fr","he","it","nl","no","pt","ru","sv","ud","zh"]
    selected_lang = st.selectbox("언어 선택 (ISO-639-1)", 
                                 options=lang_options, 
                                 help="한 번에 하나의 언어만 선택 가능합니다.")


if st.button("🔍 Search"):

    # 네이버 뉴스 API 호출
    headers = {"X-Naver-Client-Id": api_key_naver_client_id,
               "X-Naver-Client-Secret":api_key_naver_client_secret}
    naver_url = "https://openapi.naver.com/v1/search/news.json"
    naver_params = {"query": query_kor,
                    "display": 100,
                    "start": 1,
                    "sort": "sim"}
    resp = requests.get(naver_url, headers=headers, params=naver_params).json().get("items", [])

    ## 기사 링크 기준으로 중복기사 제거
    unique = []
    seen = set()
    for it in resp:
        link = it["link"]
        if link not in seen:
            seen.add(link)
            unique.append(it)

    ## 최근 24시간 기준으로 필터링
    recent_naver = []
    now_utc = datetime.now(timezone.utc)
    for it in unique:
        try:
            # RFC-1123 포맷 파싱
            pub = datetime.strptime(it["pubDate"], "%a, %d %b %Y %H:%M:%S %z")
            # UTC 기준으로 비교
            if now_utc - pub.astimezone(timezone.utc) <= timedelta(hours=24):
                recent_naver.append(it)
        except Exception:
            # 파싱 실패 시 건너뜀
            continue

    st.session_state.naver_news = recent_naver


    # 국외뉴스 API 호출
    newsapi = NewsApiClient(api_key=api_key_newsapi)
    
    params = {"from_param" : start_date,
              "to" : end_date,
              "page_size" : 100}

    if title_only:
        params["qintitle"] = query_glo
    else:
        params["q"] = query_glo

    if use_lang:
        params["language"] = selected_lang

    articles = newsapi.get_everything(**params)

    if articles['status'] == 'ok':
        # Do the Job
        st.session_state.articles = articles
        st.success(f"국내 뉴스 {len(recent_naver)}개, 글로벌 뉴스 {articles['totalResults']}개의 기사를 찾았습니다.")
        number_of_articles = len(recent_naver) + articles['totalResults']
        if number_of_articles < 30 or number_of_articles > 500:
            st.warning("⚠️뉴스가 너무 적거나 많으면 요약이 부정확할 수 있습니다. 핵심 기사만 선택하거나 검색조건을 조절해 보세요.")
    else:
        st.error(f"News API error: {articles['status']}")


if "articles" in st.session_state:

    tab1, tab2 = st.tabs(["국내", "국외"])

    with tab1:
        st.subheader("국내뉴스 (Naver API)")
        md = "| Title | Description | Date |\n"
        md += "|---|---|---|\n"
        
        for article in st.session_state.naver_news:
            title = article['title'].replace('|', '\\|').replace("<b>","").replace("</b>","")
            url = article["link"]
            desc = article["description"].replace('|', '\\|').replace("<b>","").replace("</b>","")
            date = article["pubDate"][:16]

            title_md = f"[{title}]({url})"
            md += f"| {title_md} | {desc} | {date} |\n"

        st.markdown(md, unsafe_allow_html=True)


    with tab2:
        st.subheader("국외뉴스 (News API)")

        md = "| Title | Description | Source | Date |\n"
        md += "|---|---|---|---|\n"

        for article in st.session_state.articles['articles']:
            title = article['title'].replace('|', '\\|')
            url = article['url']
            desc = (article.get("description") or "").replace('|', '\\|').replace("\n", " ").replace("\r", " ")
            source = article['source']['name']
            date = article['publishedAt'][:10]

            title_md = f"[{title}]({url})"

            md += f"| {title_md} | {desc} | {source} | {date} |\n"

        st.markdown(md, unsafe_allow_html=True)

    # 요약하러 가기
    st.write("")  
    st.write("")  
    additional_prompt = st.text_input("(선택) AI에게 요약 형태 요청",
                                      help="원하는 요약 가이드라인이 있을 경우 입력",
                                      placeholder="사용자 요약 가이드라인")
    if st.button("📝 Summarize"):
        with st.spinner("요약을 진행 중입니다… 잠시만 기다려주세요(요약 모델에 따라 30초~1분정도 소요됩니다.)"):

            articles_text = ""
            for i, article in enumerate(st.session_state.articles['articles'], 1):
                articles_text += (
                    f"{i}. Title: {article['title']}\n"
                    f"   Description: {article['description']}\n"
                    f"   URL: {article['url']}\n\n"
                )
                count = i

            for i, article in enumerate(st.session_state.naver_news, count):
                articles_text += (
                    f"{i}. Title: {article['title']}\n"
                    f"   Description: {article['description']}\n"
                    f"   URL: {article['link']}\n\n"
                )

            system_context = """
            You are an expert assistant for National Strategy Technology policy, you will carefully read them and produce a concise summary.
            """

            prompt = f"""
Group the news articles below into 3~5 major issues (depending on the number of articles) and summarize each issue.
Use a mix of Korean and international news, and you can exclude unnecessary articles.

{additional_prompt}

0. Be written in KOREAN
1. **Topic Title**: 10-20 words.
2. **Summary**: 4-5 sentence overview of the core theme and some specific content that article says.
3. **Articles**: Markdown list of titles with URLs.

Format exactly like this:

## Topic 1: <Topic Title>
**Summary:** ... \n
**Articles:**
- [Title A](URL)
- [Title B](URL)

Articles:
{articles_text}
"""
            max_token = 16384 if selected_model == "gpt-4o" else 32768
            
            response = openai.ChatCompletion.create(
                model = selected_model,
                messages = [{"role": "system", "content": system_context},
                            {"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_token,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                response_format={
                    "type": "text"
                }
            )
        st.success("요약이 완료되었습니다!")
        st.session_state["summary_md"] = response.choices[0].message.content

summary_md = st.session_state.get("summary_md")

if summary_md:
    st.markdown(summary_md, unsafe_allow_html=True)
    if st.button("📄 PDF로 다운로드"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ✅ 유니코드 폰트 등록
        pdf.add_font("NotoCJK", "", "./fonts/NotoSansCJKkr-Regular.ttf", uni=True)
        pdf.add_font("Nanum", "",     "./fonts/NanumGothic.ttf",      uni=True)
        pdf.add_font("Nanum", "B",    "./fonts/NanumGothicBold.ttf",  uni=True)

        for line in summary_md.splitlines():
            line = line.rstrip()

            # 1) 헤더 처리
            if line.startswith("## "):
                title = line[3:].strip()
                pdf.set_font("Nanum", style='B', size=14)
                pdf.write(8, title)
                pdf.ln(10)
                pdf.set_font("Nanum", size=12)
                continue

            # 2) Summary 문단 처리
            if line.startswith("**Summary:**"):
                content = line.split("**Summary:**", 1)[1].strip()
                pdf.set_font("Nanum", style='B', size=12)
                pdf.write(8, "Summary: ")
                pdf.set_font("Nanum", size=12)
                pdf.write(8, content)
                pdf.ln(8)
                continue

            # 3) Articles 블록도 따로 처리
            if "**Articles:**" in line:
                pdf.set_font("Nanum", "B", 12)
                pdf.write(8, "Articles:")
                pdf.set_font("Nanum", size=12)
                pdf.ln(6)
                continue


            # 3) 링크 리스트 항목
            m = re.match(r"- \[(.*?)\]\((.*?)\)", line)
            if m:
                title, url = m.groups()
                pdf.write(8, "• ")

                # ✅ 파란색 밑줄로 하이퍼링크 표시
                pdf.set_text_color(0, 0, 255)    # 파란색
                pdf.set_font("NotoCJK", style='U') # 밑줄
                pdf.write(8, title, link=url)

                # 스타일 되돌리기
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("NotoCJK", size=12)
                pdf.ln(8)
                continue

            # 4) 일반 텍스트
            if line:
                pdf.write(8, line)
                pdf.ln(8)

        buffer = io.BytesIO()
        pdf_data = pdf.output(dest='S').encode('latin1')
        buffer = io.BytesIO(pdf_data)

        st.download_button(
            label="Download summary.pdf",
            data=buffer,
            file_name="summary.pdf",
            mime="application/pdf"
        )