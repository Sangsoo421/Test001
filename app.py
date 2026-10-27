import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

NAME_MAX = 50
QTY_MIN, QTY_MAX = 1, 99
FILTERS = ["전체", "미완료", "완료"]

# 저장 파일. 테스트 등에서 SHOPPING_LIST_DATA 환경변수로 경로를 바꿀 수 있다.
# 주의: Streamlit Community Cloud에서는 앱이 재시작/재배포되면 이 파일이 초기화되고,
# 서버 파일 하나를 모든 접속자가 함께 쓰므로 목록도 사용자 간에 공유된다.
DATA_FILE = Path(os.environ.get("SHOPPING_LIST_DATA", Path(__file__).with_name("items.json")))

# 고정 CSS 문자열만 사용한다. 사용자 입력은 절대 여기에 넣지 않는다.
CSS = """
<style>
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 2.5rem; max-width: 640px; }
h1 { font-size: 2rem !important; }

/* 목록 행: 카드 형태, 모바일에서도 한 줄 유지 */
[class*="st-key-row_"] {
  background: #fff;
  border: 1px solid #DCE8DA;
  border-radius: 12px;
  padding: 0.35rem 0.6rem;
}
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important;
  gap: 0.4rem;
  align-items: center;
}
[class*="st-key-row_"] [data-testid="stColumn"] {
  min-width: 0 !important;
  width: auto !important;
}
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; overflow-wrap: anywhere; }
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(2),
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(3) { flex: 0 0 2.4rem !important; }
[class*="st-key-row_"] button { padding: 0.2rem 0.3rem; min-height: 2.2rem; }
[class*="st-key-row_"] [data-testid="stColumn"] > div,
[class*="st-key-row_"] [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
  height: 100%;
  justify-content: center;
}
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] { line-height: 1.3; }
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }

/* 위험 동작 버튼 */
.st-key-clear_all button, .st-key-confirm_clear_yes button, [class*="st-key-del_"] button:hover {
  color: #C62828;
  border-color: #C62828;
}

/* 하단 액션 버튼을 한 줄에 */
.st-key-actions [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
.st-key-actions [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-actions button { width: 100%; }
</style>
"""

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!~|<>$:&])")


def escape_md(text):
    """사용자 텍스트가 마크다운으로 해석되지 않도록 특수문자를 이스케이프한다."""
    return _MD_SPECIAL.sub(r"\\\1", text)


# ---------- 저장소 ----------

def _clean_item(raw):
    """파일에서 읽은 항목이 올바른 형태면 정리해서 반환하고, 아니면 None."""
    if not isinstance(raw, dict):
        return None
    name, qty = raw.get("name"), raw.get("quantity")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > NAME_MAX:
        return None
    if isinstance(qty, bool) or not isinstance(qty, int) or not QTY_MIN <= qty <= QTY_MAX:
        return None
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "name": name.strip(),
        "quantity": qty,
        "checked": raw.get("checked") is True,
        "created_at": str(raw.get("created_at") or datetime.now().isoformat(timespec="seconds")),
    }


def _parse(text):
    """JSON 문자열을 항목 목록으로 바꾼다. 형식이 틀리면 None."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    cleaned = (_clean_item(raw) for raw in data)
    return [item for item in cleaned if item]


def load_items():
    """JSON 파일에서 목록을 읽는다. 파일이 없거나 깨져 있으면 빈 목록을 돌려준다."""
    try:
        parsed = _parse(DATA_FILE.read_text(encoding="utf-8"))
    except OSError:
        return []
    return parsed if parsed is not None else []


def save_items(items):
    """목록을 JSON 파일에 쓴다. 실패해도 앱은 계속 동작하고 경고만 남긴다."""
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA_FILE)
    except OSError:
        st.session_state["save_failed"] = True
        flash("warning", "목록을 파일에 저장하지 못했어요. 이 화면에서만 유지됩니다.")
    else:
        st.session_state["save_failed"] = False


def sync_from_disk():
    """다른 접속자가 파일을 바꿨을 수 있으므로 변경 직전/화면 그리기 직전에 최신 목록을 읽는다.

    그렇지 않으면 오래된 목록으로 파일을 덮어써서 다른 사람의 변경이 사라진다.
    저장이 실패한 상태이거나 파일을 읽지 못하면 화면의 목록을 그대로 둔다.
    """
    if st.session_state.get("save_failed"):
        return
    try:
        parsed = _parse(DATA_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        parsed = []
    except OSError:
        return
    if parsed is not None:
        st.session_state["items"] = parsed


# ---------- 상태 ----------

def init_state():
    state = st.session_state
    if "items" not in state:
        state["items"] = load_items()
    state.setdefault("editing_id", None)
    state.setdefault("confirm_clear", False)


def flash(level, message):
    st.session_state["flash"] = (level, message)


def items():
    return st.session_state["items"]


def set_items(new_items):
    """목록을 새 리스트로 교체하고 저장한다. (순회 중 직접 삭제하지 않기 위해)"""
    st.session_state["items"] = new_items
    if st.session_state["editing_id"] not in {i["id"] for i in new_items}:
        st.session_state["editing_id"] = None
    save_items(new_items)


def validate(name, quantity):
    """(정리된 이름, 오류 메시지)를 돌려준다. 오류가 없으면 메시지는 None."""
    name = (name or "").strip()
    if not name:
        return name, "아이템 이름을 입력해 주세요."
    if len(name) > NAME_MAX:
        return name, f"이름은 {NAME_MAX}자 이하로 입력해 주세요. (현재 {len(name)}자)"
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not QTY_MIN <= quantity <= QTY_MAX:
        return name, f"수량은 {QTY_MIN}~{QTY_MAX} 사이의 정수로 입력해 주세요."
    return name, None


# ---------- 콜백 ----------

def on_add():
    sync_from_disk()
    state = st.session_state
    name, error = validate(state.get("new_name"), state.get("new_qty"))
    if error:
        flash("warning", error)
        return
    new_item = {
        "id": str(uuid.uuid4()),
        "name": name,
        "quantity": state["new_qty"],
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    set_items(items() + [new_item])


def on_toggle(item_id):
    sync_from_disk()
    checked = st.session_state[f"chk_{item_id}"]
    set_items([{**i, "checked": checked} if i["id"] == item_id else i for i in items()])


def on_delete(item_id):
    sync_from_disk()
    set_items([i for i in items() if i["id"] != item_id])


def on_start_edit(item_id):
    sync_from_disk()
    item = next((i for i in items() if i["id"] == item_id), None)
    if item is None:  # 그 사이 다른 접속자가 삭제했다
        return
    # 이전 수정 내용이 남지 않도록 입력값을 현재 항목 값으로 초기화한다.
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = item["quantity"]
    previous = st.session_state["editing_id"]
    if previous not in (None, item_id):
        st.session_state["full_rerun"] = True  # 다른 행의 수정 폼을 닫으려면 전체를 다시 그려야 한다
    st.session_state["editing_id"] = item_id  # 한 번에 한 항목만 수정


def on_cancel_edit():
    st.session_state["editing_id"] = None


def on_save_edit(item_id):
    sync_from_disk()
    state = st.session_state
    name, error = validate(state.get(f"edit_name_{item_id}"), state.get(f"edit_qty_{item_id}"))
    if error:
        flash("warning", error)
        return
    qty = state[f"edit_qty_{item_id}"]
    set_items([{**i, "name": name, "quantity": qty} if i["id"] == item_id else i for i in items()])
    state["editing_id"] = None


def on_clear_checked():
    sync_from_disk()
    if not any(i["checked"] for i in items()):
        flash("info", "완료한 항목이 없어요.")
        return
    set_items([i for i in items() if not i["checked"]])


def on_ask_clear_all():
    st.session_state["confirm_clear"] = True


def on_cancel_clear_all():
    st.session_state["confirm_clear"] = False


def on_confirm_clear_all():
    sync_from_disk()
    st.session_state["confirm_clear"] = False
    set_items([])


# ---------- 화면 ----------

def render_flash():
    message = st.session_state.pop("flash", None)
    if message:
        level, text = message
        getattr(st, level)(text)


def render_form():
    with st.form("add_form", clear_on_submit=True):
        name_col, qty_col = st.columns([3, 1])
        name_col.text_input("아이템 이름", placeholder="예: 우유", key="new_name")
        qty_col.number_input("수량", min_value=QTY_MIN, max_value=QTY_MAX, value=1, step=1, key="new_qty")
        st.form_submit_button("추가", type="primary", on_click=on_add)


def draw_summary(summary):
    """진행 현황 카드를 자리표시자 안에 (다시) 그린다."""
    total = len(items())
    done = sum(1 for i in items() if i["checked"])
    with summary.container(border=True):
        st.markdown(f"**전체 {total}개 중 {done}개 완료**")
        st.progress(done / total if total else 0.0)


def shown_items():
    selected = st.session_state.get("filter", "전체")
    return [i for i in items() if selected == "전체" or (selected == "완료") == i["checked"]]


def layout_signature():
    """목록 밖 화면 구성(빈 목록 안내, 필터 결과 없음 안내)이 바뀌었는지 비교하는 값."""
    return (bool(items()), bool(shown_items()))


@st.fragment
def render_row(item_id, summary):
    """행 하나를 독립적으로 다시 그린다. 항목 200개에서도 체크·삭제·수정이 그 행만 갱신하도록 fragment로 분리했다."""
    state = st.session_state
    if not state.get("in_full_run"):
        # fragment만 다시 실행된 경우: 다른 영역까지 바뀌어야 하면 전체를 다시 그린다.
        if state.pop("full_rerun", False) or state.get("layout_sig") != layout_signature():
            st.rerun()
    render_flash()
    item = next((i for i in shown_items() if i["id"] == item_id), None)
    if item is not None:
        if state["editing_id"] == item_id:
            render_edit_row(item_id)
        else:
            render_view_row(item)
    draw_summary(summary)


def render_view_row(item):
    """행 하나. 위젯·요소 수가 곧 화면 갱신 비용이므로 이름과 수량 배지는 체크박스 라벨 안에 함께 넣는다."""
    item_id = item["id"]
    text = escape_md(item["name"])
    qty = item["quantity"]
    label = f":gray[~~{text}~~] :gray-badge[x{qty}]" if item["checked"] else f"{text} :green-badge[x{qty}]"
    with st.container(key=f"row_{item_id}"):
        check_col, edit_col, del_col = st.columns(3, vertical_alignment="center")
        check_col.checkbox(
            label,
            value=item["checked"],
            key=f"chk_{item_id}",
            on_change=on_toggle,
            args=(item_id,),
        )
        edit_col.button("✏️", key=f"edit_{item_id}", on_click=on_start_edit, args=(item_id,), help="수정")
        del_col.button("🗑️", key=f"del_{item_id}", on_click=on_delete, args=(item_id,), help="삭제")


def render_edit_row(item_id):
    with st.form(f"edit_form_{item_id}"):
        name_col, qty_col = st.columns([3, 1])
        name_col.text_input("이름 수정", key=f"edit_name_{item_id}")
        qty_col.number_input("수량 수정", min_value=QTY_MIN, max_value=QTY_MAX, step=1, key=f"edit_qty_{item_id}")
        save_col, cancel_col = st.columns(2)
        save_col.form_submit_button("저장", type="primary", on_click=on_save_edit, args=(item_id,))
        cancel_col.form_submit_button("취소", on_click=on_cancel_edit)


def render_list():
    if not items():
        st.info("아직 담긴 물건이 없어요. 위에서 추가해 보세요.", icon="🛍️")
        st.session_state["layout_sig"] = layout_signature()
        return
    summary = st.empty()
    st.radio("보기", FILTERS, horizontal=True, key="filter")
    shown = shown_items()
    if not shown:
        st.caption("해당하는 항목이 없어요.")
    for item in shown:
        render_row(item["id"], summary)
    draw_summary(summary)
    st.session_state["layout_sig"] = layout_signature()


def render_actions():
    if not items():
        return
    st.divider()
    with st.container(key="actions"):
        clear_col, all_col = st.columns(2)
        clear_col.button("완료 항목 삭제", on_click=on_clear_checked)
        all_col.button("전체 삭제", key="clear_all", on_click=on_ask_clear_all)
        if st.session_state["confirm_clear"]:
            st.warning("정말 모든 항목을 삭제할까요?")
            yes_col, no_col = st.columns(2)
            yes_col.button("확인", key="confirm_clear_yes", on_click=on_confirm_clear_all)
            no_col.button("취소", key="confirm_clear_no", on_click=on_cancel_clear_all)


def main():
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🛒 쇼핑 리스트")
    init_state()
    st.session_state["in_full_run"] = True
    try:
        sync_from_disk()
        render_flash()
        render_form()
        render_list()
        render_actions()
    finally:
        st.session_state["in_full_run"] = False


main()
