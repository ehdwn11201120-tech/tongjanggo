import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
import os
import base64
import json
import urllib.request

# 텅장고 3주차 Prototype
st.set_page_config(page_title="텅장고", page_icon="🥬", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
FRIDGE_FILE = DATA_DIR / "fridge.csv"
EXPENSE_FILE = DATA_DIR / "expenses.csv"
INGREDIENT_FILE = DATA_DIR / "ingredients.csv"
RECIPE_FILE = DATA_DIR / "recipes.csv"


def load_csv(path, columns):
    if path.exists():
        return pd.read_csv(path, encoding="utf-8-sig")
    df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


def save_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def money(value):
    return f"{int(value):,}원"


# 가격과 레시피를 별도 CSV에서 불러온다.
def load_ingredient_data():
    default = pd.DataFrame({
        "재료": ["계란", "김치", "대파", "밥", "삼겹살", "라면", "두부", "참치캔", "양파"],
        "가격": [400, 800, 500, 500, 5000, 1000, 1500, 2000, 1000]
    })
    if not INGREDIENT_FILE.exists():
        default.to_csv(INGREDIENT_FILE, index=False, encoding="utf-8-sig")
    return pd.read_csv(INGREDIENT_FILE, encoding="utf-8-sig")


def load_recipe_data():
    if not RECIPE_FILE.exists():
        default = pd.DataFrame([
            ["김치 계란 볶음밥", "김치|계란|밥|대파", 550, 15, "밥과 김치를 볶은 뒤 계란과 대파를 넣습니다."],
            ["김치 삼겹살 볶음", "김치|삼겹살|대파", 650, 20, "삼겹살을 먼저 굽고 김치와 대파를 넣어 볶습니다."],
            ["계란 라면", "라면|계란|대파", 570, 10, "라면을 끓인 뒤 계란과 대파를 넣습니다."],
            ["두부 김치", "두부|김치|대파", 380, 15, "두부를 데우고 김치를 볶아 함께 먹습니다."],
            ["참치 계란 덮밥", "참치캔|계란|밥|양파", 600, 15, "참치와 양파를 볶고 계란을 넣어 밥 위에 올립니다."]
        ], columns=["이름", "재료", "칼로리", "시간", "방법"])
        default.to_csv(RECIPE_FILE, index=False, encoding="utf-8-sig")
    df = pd.read_csv(RECIPE_FILE, encoding="utf-8-sig")
    return [{"이름": r["이름"], "재료": str(r["재료"]).split("|"), "칼로리": int(r["칼로리"]), "시간": int(r["시간"]), "방법": r["방법"]} for _, r in df.iterrows()]


def vision_guess(uploaded_file):
    """선택 기능: OPENAI_API_KEY가 있을 때 사진을 Vision 모델로 분석한다.
    키가 없으면 사용자가 직접 재료명을 확인·입력할 수 있도록 None을 반환한다.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY", "").strip()
        except Exception:
            api_key = ""
    if not api_key:
        return None, "OPENAI_API_KEY가 없어 직접 확인 입력 모드로 진행합니다."
    image_bytes = uploaded_file.getvalue()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = uploaded_file.type or "image/jpeg"
    payload = {"model":"gpt-4o-mini", "messages":[{"role":"user","content":[
        {"type":"text","text":"영수증에서 전체 결제금액, 대표 항목, 결제일을 추출하세요. 반드시 JSON 하나만 반환하세요: {\"amount\": 숫자, \"item\": \"식재료\", \"date\": \"YYYY-MM-DD\"}. 읽을 수 없는 값은 0 또는 빈 문자열로 반환하세요."},
        {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}}]}], "max_tokens":100}
    req=urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data=json.loads(res.read().decode())
        text=data["choices"][0]["message"]["content"].strip()
        return text, "AI 이미지 인식 결과입니다. 반드시 확인 후 저장하세요."
    except Exception as e:
        return None, f"이미지 인식에 실패하여 직접 입력 모드로 전환합니다: {e}"

ingredient_df = load_ingredient_data()
PRICES = dict(zip(ingredient_df["재료"].astype(str).str.strip(), ingredient_df["가격"]))
RECIPES = load_recipe_data()

fridge = load_csv(FRIDGE_FILE, ["재료", "수량", "유통기한"])
# 수량은 숫자 또는 문자로 입력할 수 있으므로 문자열 열로 통일
if "수량" in fridge.columns:
    fridge["수량"] = fridge["수량"].fillna("").astype(str)
expenses = load_csv(EXPENSE_FILE, ["날짜", "항목", "금액"])

st.title("🥬 텅장고")
st.caption("냉장고를 비우고, 식비를 지키는 자취생 앱")
st.info("💡 냉장고 재료를 등록하면 유통기한과 예산을 고려해 메뉴를 추천해드려요.")

# 상단 요약
month_total = pd.to_numeric(expenses["금액"], errors="coerce").fillna(0).sum() if not expenses.empty else 0
summary1, summary2, summary3 = st.columns(3)
summary1.metric("등록된 냉장고 재료", f"{len(fridge)}개")
summary2.metric("누적 식비 지출", money(month_total))
summary3.metric("유통기한 임박 재료", f"{sum((pd.to_datetime(fridge['유통기한'], errors='coerce').dt.date - date.today()).apply(lambda x: x.days if pd.notna(x) else 999) <= 3) if not fridge.empty else 0}개")

tab1, tab_receipt, tab2, tab3 = st.tabs(["🥬 냉장고 관리", "🧾 영수증 인식", "🍳 예산 맞춤 메뉴", "💰 예산·가계부"])

with tab1:
    st.header("내 냉장고")
    st.caption("재료를 등록하면 유통기한 임박 여부를 자동으로 확인합니다.")
    with st.form("add_food", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        food = c1.text_input("재료 이름", placeholder="예: 계란")
        quantity = c2.text_input("수량", placeholder="예: 6개")
        expiry = c3.date_input("유통기한", value=date.today())
        add = st.form_submit_button("재료 추가")
    if add:
        clean_food = food.strip().replace(" ", "")
        existing_foods = fridge["재료"].astype(str).str.strip().str.replace(" ", "", regex=False).tolist()
        if not clean_food or not quantity.strip():
            st.warning("재료 이름과 수량을 모두 입력해주세요.")
        elif clean_food in existing_foods:
            st.warning("이미 등록된 재료입니다. 기존 재료의 수량을 확인해주세요.")
        else:
            fridge = pd.concat([fridge, pd.DataFrame([{"재료": clean_food, "수량": quantity.strip(), "유통기한": expiry.isoformat()}])], ignore_index=True)
            save_csv(fridge, FRIDGE_FILE)
            st.success(f"{clean_food}을(를) 추가했습니다.")
            st.rerun()

    if fridge.empty:
        st.info("등록된 재료가 없습니다.")
    else:
        today = date.today()
        urgent_rows = []
        expired_rows = []
        for i, row in fridge.iterrows():
            expiry_date = pd.to_datetime(row["유통기한"], errors="coerce").date()
            days = (expiry_date - today).days
            if days < 0:
                expired_rows.append(i)
            elif days <= 3:
                urgent_rows.append((i, row["재료"], days))

        if urgent_rows:
            st.warning("⚠️ 유통기한 임박 재료")
            st.write(" · ".join([f"{name}: {days}일 남음" for _, name, days in urgent_rows]))
        if expired_rows:
            st.error(f"유통기한이 지난 재료 {len(expired_rows)}개가 있습니다. 메뉴 추천에서 자동 제외됩니다.")

        st.subheader("냉장고 재료 목록")
        for i, row in fridge.iterrows():
            expiry_date = pd.to_datetime(row["유통기한"], errors="coerce").date()
            days = (expiry_date - today).days
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.write(f"**{row['재료']}**")
            c2.write(f"수량: {row['수량']}")
            if days < 0:
                c3.error("유통기한 지남")
            elif days <= 3:
                c3.warning(f"{days}일 남음")
            else:
                c3.success(f"{days}일 남음")
            if c4.button("삭제", key=f"delete_{i}"):
                fridge = fridge.drop(i).reset_index(drop=True)
                save_csv(fridge, FRIDGE_FILE)
                st.rerun()

        st.subheader("재료 수량 수정")
        edit_index = st.selectbox("수정할 재료", list(fridge.index), format_func=lambda i: str(fridge.loc[i, "재료"]))
        new_quantity = st.text_input("새 수량", value=str(fridge.loc[edit_index, "수량"]), key="new_quantity")
        if st.button("수량 수정 저장"):
            if not new_quantity.strip():
                st.warning("수량을 입력해주세요.")
            else:
                fridge.loc[edit_index, "수량"] = new_quantity.strip()
                save_csv(fridge, FRIDGE_FILE)
                st.success("수량을 수정했습니다.")
                st.rerun()

with tab_receipt:
    st.header("🧾 영수증으로 지출 등록")
    st.caption("영수증 사진을 올리면 금액·항목·날짜를 확인한 뒤 가계부에 저장할 수 있습니다.")
    uploaded = st.file_uploader("영수증 사진 업로드", type=["jpg", "jpeg", "png"], key="receipt_photo")
    if uploaded:
        st.image(uploaded, caption="업로드한 영수증", use_container_width=True)
        if "receipt_guess" not in st.session_state or st.button("영수증 다시 분석"):
            with st.spinner("영수증을 분석하고 있습니다..."):
                guess, message = vision_guess(uploaded)
            try:
                parsed=json.loads(guess) if guess else {}
            except Exception:
                parsed={}
            st.session_state["receipt_guess"] = parsed
            st.session_state["receipt_message"] = message
        parsed=st.session_state.get("receipt_guess", {})
        st.info(st.session_state.get("receipt_message", "영수증 내용을 확인하세요."))
        r1,r2,r3=st.columns(3)
        receipt_item=r1.text_input("항목 확인·수정", value=str(parsed.get("item", "식재료")), key="receipt_item")
        receipt_amount=r2.number_input("금액 확인·수정", min_value=0, value=int(parsed.get("amount",0) or 0), step=500, key="receipt_amount")
        try: default_date=date.fromisoformat(str(parsed.get("date", date.today().isoformat())))
        except Exception: default_date=date.today()
        receipt_date=r3.date_input("날짜 확인·수정", value=default_date, key="receipt_date")
        if st.button("확인한 영수증을 가계부에 저장", type="primary"):
            if receipt_amount <= 0:
                st.warning("금액을 확인하거나 직접 입력해주세요.")
            else:
                expenses=pd.concat([expenses,pd.DataFrame([{"날짜":receipt_date.isoformat(),"항목":receipt_item.strip() or "식재료","금액":receipt_amount}])],ignore_index=True)
                save_csv(expenses,EXPENSE_FILE)
                st.success("영수증 지출을 가계부에 저장했습니다.")
                st.session_state.pop("receipt_guess",None)
                st.rerun()
    else:
        st.info("식재료 구매 영수증 사진을 업로드해보세요.")

with tab2:
    st.header("냉장고 재료로 메뉴 추천")
    st.caption("유통기한 임박 재료와 보유 재료를 많이 활용하는 메뉴를 우선 추천합니다.")
    daily_budget = st.number_input("오늘 추가 구매 예산", min_value=0, value=10000, step=500)
    owned = set()
    if not fridge.empty:
        for _, row in fridge.iterrows():
            expiry = pd.to_datetime(row["유통기한"], errors="coerce")
            if pd.notna(expiry) and (expiry.date() - date.today()).days >= 0:
                owned.add(str(row["재료"]).strip().replace(" ", ""))
    st.write("현재 재료:", ", ".join(sorted(owned)) if owned else "없음")
    if st.button("예산에 맞는 메뉴 추천", type="primary"):
        results = []
        urgent_foods = set()
        if not fridge.empty:
            for _, row in fridge.iterrows():
                expiry = pd.to_datetime(row["유통기한"], errors="coerce")
                if pd.notna(expiry) and 0 <= (expiry.date() - date.today()).days <= 3:
                    urgent_foods.add(str(row["재료"]).strip().replace(" ", ""))
        for recipe in RECIPES:
            recipe_foods = [x.strip().replace(" ", "") for x in recipe["재료"]]
            missing = [x for x in recipe["재료"] if x not in owned]
            cost = sum(PRICES.get(x, 0) for x in missing)
            used_count = len(recipe["재료"]) - len(missing)
            urgent_count = sum(1 for x in recipe_foods if x in urgent_foods and x in owned)
            score = used_count * 100 + urgent_count * 50 - cost
            if cost <= daily_budget:
                results.append((score, used_count, urgent_count, cost, recipe, missing))
        results.sort(key=lambda x: (-x[0], x[3]))
        if not results:
            st.error("현재 예산으로 만들 수 있는 메뉴가 없습니다.")
            st.info("오늘 추가 구매 예산을 늘리거나 냉장고 재료를 더 등록해보세요.")
        for n, (_, used_count, urgent_count, cost, recipe, missing) in enumerate(results[:3], 1):
            st.subheader(f"{n}. {recipe['이름']}")
            a, b, c = st.columns(3)
            a.metric("예상 지출", money(cost))
            b.metric("메뉴 후 남은 예산", money(daily_budget - cost))
            c.metric("예상 칼로리", f"{recipe['칼로리']} kcal")
            st.write("필요한 재료:", ", ".join(recipe["재료"]))
            st.write("추가 구매 재료:", ", ".join(missing) if missing else "없음")
            if urgent_count > 0:
                st.info(f"추천 이유: 유통기한 임박 재료 {urgent_count}개를 먼저 사용할 수 있습니다.")
            else:
                st.caption(f"추천 이유: 냉장고 재료 {used_count}개를 활용합니다.")
            st.write(f"조리 시간: {recipe['시간']}분 | 조리 방법: {recipe['방법']}")
            st.divider()

with tab3:
    st.header("예산·가계부")
    st.caption("이번 주 식비 예산과 실제 지출을 비교해보세요.")
    weekly_budget = st.number_input("이번 주 식비 예산", min_value=0, value=70000, step=5000)
    total = pd.to_numeric(expenses["금액"], errors="coerce").fillna(0).sum() if not expenses.empty else 0
    left = weekly_budget - total
    a, b, c = st.columns(3)
    a.metric("이번 주 예산", money(weekly_budget))
    b.metric("현재 지출", money(total))
    c.metric("남은 예산", money(left))
    st.progress(min(max(float(total / weekly_budget), 0.0), 1.0) if weekly_budget else 0.0)
    st.caption(f"예산 사용률: {(total / weekly_budget * 100):.1f}%" if weekly_budget else "예산을 입력해주세요.")

    with st.form("expense_form", clear_on_submit=True):
        d1, d2, d3 = st.columns(3)
        category = d1.selectbox("지출 항목", ["식재료", "배달음식", "외식", "간식", "기타"])
        amount = d2.number_input("지출 금액", min_value=0, value=0, step=500)
        expense_date = d3.date_input("지출 날짜", value=date.today())
        save = st.form_submit_button("지출 저장")
    if save:
        if amount <= 0:
            st.warning("지출 금액을 입력해주세요.")
        else:
            expenses = pd.concat([expenses, pd.DataFrame([{"날짜": expense_date.isoformat(), "항목": category, "금액": amount}])], ignore_index=True)
            save_csv(expenses, EXPENSE_FILE)
            st.success("지출을 저장했습니다.")
            st.rerun()

    if expenses.empty:
        st.info("아직 지출 내역이 없습니다.")
    else:
        st.subheader("지출 내역")
        st.dataframe(expenses, use_container_width=True, hide_index=True)

        st.subheader("지출 내역 삭제")
        expense_options = list(expenses.index)
        selected_expense = st.selectbox(
            "삭제할 지출을 선택하세요",
            expense_options,
            format_func=lambda i: (
                f"{i + 1}. {expenses.loc[i, '날짜']} / "
                f"{expenses.loc[i, '항목']} / "
                f"{int(expenses.loc[i, '금액']):,}원"
            )
        )
        if st.button("선택한 지출 삭제"):
            expenses = expenses.drop(selected_expense).reset_index(drop=True)
            save_csv(expenses, EXPENSE_FILE)
            st.success("선택한 지출 내역을 삭제했습니다.")
            st.rerun()

        st.subheader("항목별 지출")
        if expenses.empty:
            st.info("삭제 후 남은 지출 내역이 없습니다.")
        else:
            st.bar_chart(expenses.groupby("항목")["금액"].sum())

st.divider()
st.caption("※ 가격과 칼로리는 프로젝트용 예시 데이터입니다. 실제 가격과 다를 수 있습니다.")
