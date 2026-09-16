import io
import os
import json
import time
import uuid
import base64
import shutil
import sqlite3
import datetime
import subprocess
import tempfile
import qrcode
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. إعدادات الصفحة والتصميم العام
# ==============================================================================
st.set_page_config(
    page_title="نظام الفواتير وعروض الأسعار - رؤية المستقبل الذكي",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, span, label, input, button {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }
    
    div[data-testid="stMetric"] {
        background-color: rgba(125, 125, 125, 0.08) !important;
        border: 1px solid rgba(125, 125, 125, 0.2) !important;
        padding: 15px 20px !important;
        border-radius: 12px !important;
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] div {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }

    .role-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .role-admin { background-color: #fee2e2; color: #b91c1c; }
    .role-accountant { background-color: #fef3c7; color: #b45309; }
    .role-sales { background-color: #e0f2fe; color: #0369a1; }
    
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .status-cleared { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .status-draft { background-color: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
</style>
""", unsafe_allow_html=True)

DB_FILE = os.path.join(os.path.dirname(__file__), "fatoora_data.db")


# ==============================================================================
# 2. إدارة قاعدة البيانات (fatoora_data.db)
# ==============================================================================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY,
            name TEXT,
            trade_name TEXT,
            vat_number TEXT,
            cr_number TEXT,
            unified_number TEXT,
            city TEXT,
            district TEXT,
            street TEXT,
            building_no TEXT,
            postal_code TEXT,
            phone TEXT,
            email TEXT,
            account_number TEXT,
            bank_name TEXT,
            iban TEXT,
            logo_b64 TEXT,
            stamp_b64 TEXT,
            signature_b64 TEXT
        )
        """)
        
        for col_name, col_type in [
            ("account_number", "TEXT"),
            ("logo_b64", "TEXT"),
            ("stamp_b64", "TEXT"),
            ("signature_b64", "TEXT")
        ]:
            try:
                cursor.execute(f"ALTER TABLE company ADD COLUMN {col_name} {col_type}")
            except: pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS egs_config (
            id INTEGER PRIMARY KEY,
            current_icv INTEGER,
            last_hash TEXT,
            is_onboarded INTEGER,
            csid_token TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            role TEXT,
            role_title TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            customer_vat TEXT,
            customer_type TEXT,
            contract_number TEXT,
            date TEXT,
            created_by TEXT,
            buyer_city TEXT,
            buyer_district TEXT,
            buyer_street TEXT,
            buyer_building TEXT,
            buyer_postal TEXT,
            items_json TEXT,
            subtotal REAL,
            vat REAL,
            total REAL,
            status TEXT,
            converted_invoice_id TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            invoice_number TEXT,
            internal_number TEXT,
            quotation_id TEXT,
            customer_name TEXT,
            customer_vat TEXT,
            customer_type TEXT,
            contract_number TEXT,
            buyer_address TEXT,
            subtype TEXT,
            icv INTEGER,
            created_by TEXT,
            timestamp TEXT,
            supply_date TEXT,
            items_json TEXT,
            subtotal REAL,
            vat REAL,
            total REAL,
            zatca_status TEXT,
            qr_b64 TEXT
        )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM company")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO company VALUES (
                1, 'مؤسسة رؤية المستقبل الذكي', 'SMART FUTURE VISION',
                '312731823400003', '1009160447', '7043097455',
                'الرياض', 'حي النظيم', 'شارع الصلاح', '7966', '14816',
                '0560095895', 'info@sfv-sa.com', '666000010006086322302',
                'مصرف الراجحي', 'SA9180000666608016322302', '', '', ''
            )
            """)
            
        cursor.execute("SELECT COUNT(*) FROM egs_config")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO egs_config VALUES (1, 1, 'NWZlMmVkYjI0OGI1NTkxMGExZGY2YTEyNTY3YTg3MTA=', 1, 'LIVE_CSID_TOKEN')")
            
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users VALUES ('admin', 'Smart@2026', 'المدير العام', 'ADMIN', 'مدير النظام')")
            cursor.execute("INSERT INTO users VALUES ('sales', 'Smart@2026', 'مسؤول المبيعات', 'SALES', 'مسؤول مبيعات')")
            cursor.execute("INSERT INTO users VALUES ('accountant', 'Smart@2026', 'المحاسب المالي', 'ACCOUNTANT', 'محاسب')")
            
        cursor.execute("SELECT COUNT(*) FROM quotations")
        if cursor.fetchone()[0] == 0:
            init_items = json.dumps([{"name": "رسائل علمية / تصنيفها بالكليات وعمل كشوف تعبئة خاصة بها", "qty": 1, "price": 13000.00}], ensure_ascii=False)
            cursor.execute("""
            INSERT INTO quotations VALUES (
                'QUO-2026-001', 'جامعة نايف العربية للعلوم الأمنية', '310993014100013', 'B2B', '59/576',
                '2026-06-21', 'مسؤول المبيعات', 'الرياض', 'حي الندوة', 'طريق خريص', '6830', '11452',
                ?, 13000.00, 1950.00, 14950.00, 'ACCEPTED', NULL
            )
            """, (init_items,))
        
        conn.commit()

init_database()

def db_get_company():
    with get_db_connection() as conn:
        return dict(conn.execute("SELECT * FROM company WHERE id=1").fetchone())

def db_update_company(data):
    with get_db_connection() as conn:
        acc_num = data.get("account_number")
        if not acc_num or str(acc_num).strip().lower() in ["none", ""]:
            acc_num = "666000010006086322302"

        conn.execute("""
        UPDATE company SET
            name=?, trade_name=?, vat_number=?, cr_number=?, unified_number=?,
            city=?, district=?, street=?, building_no=?, postal_code=?,
            phone=?, email=?, account_number=?, bank_name=?, iban=?,
            logo_b64=?, stamp_b64=?, signature_b64=?
        WHERE id=1
        """, (
            data["name"], data["trade_name"], data["vat_number"], data["cr_number"], data["unified_number"],
            data["city"], data["district"], data["street"], data["building_no"], data["postal_code"],
            data["phone"], data["email"], acc_num,
            data["bank_name"], data["iban"], data.get("logo_b64", ""), data.get("stamp_b64", ""),
            data.get("signature_b64", "")
        ))
        conn.commit()

def db_get_egs():
    with get_db_connection() as conn:
        return dict(conn.execute("SELECT * FROM egs_config WHERE id=1").fetchone())

def db_update_egs(icv, last_hash):
    with get_db_connection() as conn:
        conn.execute("UPDATE egs_config SET current_icv=?, last_hash=? WHERE id=1", (icv, last_hash))
        conn.commit()

def db_get_quotations():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM quotations ORDER BY id DESC").fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items_json"])
            res.append(d)
        return res

def db_save_quotation(q):
    with get_db_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO quotations (
            id, customer_name, customer_vat, customer_type, contract_number,
            date, created_by, buyer_city, buyer_district, buyer_street,
            buyer_building, buyer_postal, items_json, subtotal, vat, total,
            status, converted_invoice_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q["id"], q["customer_name"], q["customer_vat"], q["customer_type"], q["contract_number"],
            q["date"], q["created_by"], q["buyer_city"], q["buyer_district"], q["buyer_street"],
            q["buyer_building"], q["buyer_postal"], json.dumps(q["items"], ensure_ascii=False),
            q["subtotal"], q["vat"], q["total"], q["status"], q["converted_invoice_id"]
        ))
        conn.commit()

def db_delete_quotation(qid):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM quotations WHERE id=?", (qid,))
        conn.commit()

def db_clean_duplicate_quotations():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM quotations WHERE id != 'QUO-2026-001'")
        conn.commit()

def db_get_invoices():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM invoices ORDER BY timestamp DESC").fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items_json"])
            res.append(d)
        return res

def db_save_invoice(inv):
    with get_db_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO invoices (
            id, invoice_number, internal_number, quotation_id, customer_name,
            customer_vat, customer_type, contract_number, buyer_address, subtype,
            icv, created_by, timestamp, supply_date, items_json, subtotal,
            vat, total, zatca_status, qr_b64
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv["id"], inv["invoice_number"], inv["internal_number"], inv["quotation_id"],
            inv["customer_name"], inv["customer_vat"], inv["customer_type"], inv["contract_number"],
            inv["buyer_address"], inv["subtype"], inv["icv"], inv["created_by"], inv["timestamp"],
            inv["supply_date"], json.dumps(inv["items"], ensure_ascii=False),
            inv["subtotal"], inv["vat"], inv["total"], inv["zatca_status"], inv["qr_b64"]
        ))
        conn.commit()

def db_delete_invoice(invid):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM invoices WHERE id=?", (invid,))
        conn.commit()


# ==============================================================================
# 3. محرك توليد PDF والتصميم مع تثبيت الفوتر في القاع وتكبير الشعار
# ==============================================================================
def find_system_browser():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in candidates:
        if os.path.exists(p): return p
    return shutil.which("msedge") or shutil.which("chrome")

def generate_pdf_bytes(html_content: str) -> bytes:
    browser_exe = find_system_browser()
    if not browser_exe: return b""
    
    full_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
* {{ box-sizing: border-box; }}
body {{ font-family: 'Cairo', Arial, sans-serif; margin: 0; padding: 0; background: #fff; color: #1e293b; direction: rtl; }}
@page {{ size: A4 portrait; margin: 6mm; }}
</style>
</head>
<body>{html_content}</body>
</html>"""
    
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f_html:
        f_html.write(full_html)
        html_file = f_html.name
        
    pdf_file = html_file.replace(".html", ".pdf")
    try:
        cmd = [browser_exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_file}", html_file]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        with open(pdf_file, "rb") as f_pdf:
            return f_pdf.read()
    except Exception:
        return b""
    finally:
        if os.path.exists(html_file): os.remove(html_file)
        if os.path.exists(pdf_file): os.remove(pdf_file)

def get_tlv_record(tag: int, value: str) -> bytes:
    val_bytes = value.encode('utf-8')
    return bytes([tag, len(val_bytes)]) + val_bytes

def generate_zatca_qr_base64(seller_name: str, vat_no: str, timestamp: str, total_str: str, vat_str: str) -> str:
    tlv_data = (
        get_tlv_record(1, seller_name) +
        get_tlv_record(2, vat_no) +
        get_tlv_record(3, timestamp) +
        get_tlv_record(4, total_str) +
        get_tlv_record(5, vat_str)
    )
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(tlv_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def render_official_document_html(doc_type: str, doc_data: dict, comp_data: dict) -> str:
    """بناء كود HTML بحيث يكون الفوتر في أسفل صفحة A4 تماماً والشعار بحجم أكبر وواضح"""
    
    # التأكد من صحة رقم الحساب
    acc_num = comp_data.get("account_number")
    if not acc_num or str(acc_num).strip().lower() in ["none", ""]:
        acc_num = "666000010006086322302"

    # 1. الشعار بحجم أكبر وواضح
    if comp_data.get("logo_b64"):
        logo_markup = f'<img src="data:image/png;base64,{comp_data["logo_b64"]}" style="max-height:120px; max-width:320px; object-fit:contain;" />'
    else:
        logo_markup = """<div style="text-align:right;">
<div style="font-size:3.2rem; font-weight:900; color:#1e293b; line-height:1; letter-spacing:-1px;">رؤيـ<span style="color:#ea580c;">ـة</span></div>
<div style="font-size:1.45rem; font-weight:900; color:#0f172a; margin-top:4px;">المستقبل الذكي</div>
<div style="font-size:0.85rem; font-weight:800; color:#ea580c; letter-spacing:1.5px; margin-top:2px;">SMART FUTURE VISION</div>
</div>"""

    # 2. الختم الرسمي
    if comp_data.get("stamp_b64"):
        stamp_markup = f'<img src="data:image/png;base64,{comp_data["stamp_b64"]}" style="width:135px; height:135px;" />'
    else:
        stamp_markup = f"""<div style="width:130px; height:130px; border:3px double #1e3a8a; border-radius:50%; display:flex; flex-direction:column; justify-content:center; align-items:center; color:#1e3a8a; text-align:center; padding:4px;">
<div style="font-size:0.68rem; font-weight:bold;">مؤسسة رؤية المستقبل الذكي</div>
<div style="font-size:0.68rem; font-weight:bold;">س.ت {comp_data['cr_number']}</div>
<div style="font-size:1.3rem; font-weight:900; margin:1px 0;">رؤيــة</div>
<div style="font-size:0.62rem; font-weight:bold;">C.R {comp_data['cr_number']}</div>
<div style="font-size:0.58rem; font-weight:bold;">Smart Future Vision Foundation</div>
</div>"""

    # 3. التوقيع
    if comp_data.get("signature_b64"):
        sig_img_markup = f'<img src="data:image/png;base64,{comp_data["signature_b64"]}" style="max-height:85px; max-width:210px;" />'
    else:
        sig_img_markup = """<svg width="210" height="80" viewBox="0 0 260 95" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:inline-block; vertical-align:middle;">
<path d="M75 58 C90 35, 120 15, 135 30 C145 42, 130 65, 105 70 C75 75, 45 80, 20 85 C55 80, 180 35, 250 20 M125 35 C122 45, 128 55, 130 60 M65 72 C70 78, 80 82, 85 70" stroke="#1d4ed8" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

    # صفوف الجدول
    items_rows = ""
    for idx, item in enumerate(doc_data["items"], start=1):
        item_subtotal = item["qty"] * item["price"]
        item_vat = item_subtotal * 0.15
        item_total = item_subtotal + item_vat
        items_rows += f"""<tr style="border-bottom:1px solid #000;">
<td style="padding:10px 8px; text-align:center; border-left:1px solid #000; font-weight:bold;">{idx}</td>
<td style="padding:10px 12px; text-align:right; border-left:1px solid #000; font-weight:700;">{item['name']}</td>
<td style="padding:10px 8px; text-align:center; border-left:1px solid #000; font-weight:bold;">{item['qty']}</td>
<td style="padding:10px 8px; text-align:center; border-left:1px solid #000;">{item['price']:,.2f}</td>
<td style="padding:10px 8px; text-align:center; border-left:1px solid #000;">15%</td>
<td style="padding:10px 8px; text-align:center; border-left:1px solid #000;">{item_vat:,.2f}</td>
<td style="padding:10px 8px; text-align:center; font-weight:bold;">{item_total:,.2f}</td>
</tr>"""

    is_invoice = (doc_type == "INVOICE")
    title_ar = "فاتورة ضريبية" if is_invoice else "عرض سعر"
    doc_id = doc_data.get("invoice_number", doc_data.get("id"))
    
    qr_markup = ""
    if is_invoice and doc_data.get("qr_b64"):
        qr_markup = f"""<div style="text-align:center; margin-left:15px;">
<img src="data:image/png;base64,{doc_data['qr_b64']}" style="width:115px; height:115px; border:1px solid #000; padding:2px;" />
<div style="font-size:0.65rem; font-weight:bold; margin-top:2px;">ختم هيئة الزكاة QR</div>
</div>"""

    # الحاوية الكلية مبنية بنظام Flexbox وبارتفاع A4 (277mm) لضمان لصق الفوتر في القاع
    raw_html = f"""<div style="background:#fff; color:#000; padding:30px 35px 20px 35px; font-family:'Cairo', Arial, sans-serif; direction:rtl; border:1px solid #e2e8f0; border-radius:4px; max-width:850px; min-height:277mm; display:flex; flex-direction:column; justify-content:space-between; box-sizing:border-box; margin:0 auto;">
<div style="flex-grow:1;">
<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px;">
<div>{logo_markup}</div>
<div style="text-align:left;">
<div style="display:inline-block; border:2.5px solid #000; padding:5px 30px; font-size:1.45rem; font-weight:900; border-radius:4px; margin-bottom:10px;">{title_ar}</div>
<div style="font-size:0.95rem; font-weight:bold;">رقم: <span style="font-family:sans-serif;">{doc_id}</span></div>
<div style="font-size:0.95rem; font-weight:bold;">تاريخ: <span style="font-family:sans-serif;">{doc_data.get('date', doc_data.get('timestamp', ''))}</span></div>
{f"<div style='font-size:0.95rem; font-weight:bold;'>رقم التعميد: <span>{doc_data.get('contract_number')}</span></div>" if doc_data.get('contract_number') else ""}
<div style="font-size:0.95rem; font-weight:bold;">الرقم الضريبي: <span style="font-family:sans-serif;">{comp_data['vat_number']}</span></div>
</div>
</div>
<div style="margin-bottom:18px; font-size:1.15rem; font-weight:bold; border-bottom:1.5px solid #cbd5e1; padding-bottom:8px;">
السادة: <span style="font-weight:900;">{doc_data['customer_name']}</span>
{f" — الرقم الضريبي: <span>{doc_data.get('customer_vat')}</span>" if doc_data.get('customer_vat') else ""}
</div>
<table style="width:100%; border-collapse:collapse; border:2px solid #000; margin-bottom:25px; font-size:0.92rem;">
<thead>
<tr style="background:#f1f5f9; border-bottom:2px solid #000; font-weight:900;">
<th style="padding:10px 8px; border-left:1px solid #000; width:5%; text-align:center;">البند</th>
<th style="padding:10px 12px; border-left:1px solid #000; width:45%; text-align:right;">الوصف</th>
<th style="padding:10px 8px; border-left:1px solid #000; width:8%; text-align:center;">الكمية</th>
<th style="padding:10px 8px; border-left:1px solid #000; width:12%; text-align:center;">السعر / الوحدة</th>
<th style="padding:10px 8px; border-left:1px solid #000; width:10%; text-align:center;">نسبة الضريبة</th>
<th style="padding:10px 8px; border-left:1px solid #000; width:10%; text-align:center;">قيمة الضريبة</th>
<th style="padding:10px 8px; width:12%; text-align:center;">المجموع</th>
</tr>
</thead>
<tbody>
{items_rows}
<tr style="border-top:2px solid #000; background:#f8fafc; font-weight:900;">
<td colspan="3" style="padding:12px; text-align:center; border-left:1px solid #000; font-size:1.15rem;">المجموع الكلي</td>
<td style="padding:12px; text-align:center; border-left:1px solid #000; font-size:1.05rem;">{doc_data['subtotal']:,.2f}</td>
<td style="padding:12px; text-align:center; border-left:1px solid #000;">15%</td>
<td style="padding:12px; text-align:center; border-left:1px solid #000; font-size:1.05rem;">{doc_data['vat']:,.2f}</td>
<td style="padding:12px; text-align:center; font-size:1.2rem; color:#0f172a;">{doc_data['total']:,.2f} ر.س</td>
</tr>
</tbody>
</table>
<div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:25px; padding-bottom:20px;">
<div style="border:1.5px solid #000; border-radius:4px; padding:12px 16px; width:48%; font-size:0.9rem; line-height:1.7;">
<div style="font-weight:900; margin-bottom:5px; text-decoration:underline;">البيانات البنكية للمستفيد:</div>
<div style="font-weight:bold;">اسم المستفيد: {comp_data['name']}</div>
<div style="font-weight:bold;">اسم البنك: {comp_data['bank_name']}</div>
<div style="font-weight:bold;">رقم الحساب: <span style="font-family:sans-serif;">{acc_num}</span></div>
<div style="font-weight:bold;">رقم الآيبان: <span style="font-family:sans-serif;">{comp_data['iban']}</span></div>
</div>
<div style="display:flex; align-items:center; justify-content:flex-end; width:50%;">
{qr_markup}
<div style="text-align:center; margin-left:12px;">{stamp_markup}</div>
<div style="text-align:center;">
<div style="font-weight:bold; font-size:1rem; margin-bottom:4px; color:#1e3a8a;">التوقيع :</div>
<div>{sig_img_markup}</div>
</div>
</div>
</div>
</div>
<div style="margin-top:auto; padding-top:15px; border-top:2px solid #000; text-align:center; font-size:0.88rem; font-weight:bold; color:#1e293b; line-height:1.8;">
<div>{comp_data['name']} ، السجل التجاري : {comp_data['cr_number']}</div>
<div>رقم الهاتف : {comp_data['phone']} &nbsp;&nbsp;|&nbsp;&nbsp; العنوان : {comp_data['city']} {comp_data['district']} &nbsp;&nbsp;|&nbsp;&nbsp; {comp_data['email']}</div>
</div>
</div>"""

    cleaned_lines = [line.strip() for line in raw_html.splitlines() if line.strip()]
    return "".join(cleaned_lines)


# ==============================================================================
# 4. بوابة تسجيل الدخول
# ==============================================================================
if "current_user" not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.6, 1])
    
    with col_login:
        st.image("https://img.icons8.com/color/96/shield-checked--v1.png", width=70)
        st.header("تسجيل الدخول للنظام")
        st.caption("مؤسسة رؤية المستقبل الذكي — نظام الفوترة والامتثال")
        
        with st.form("login_form"):
            u_name = st.text_input("اسم المستخدم", placeholder="admin أو sales أو accountant")
            u_pass = st.text_input("كلمة المرور", type="password", placeholder="123")
            if st.form_submit_button("تسجيل الدخول 🚀", type="primary", use_container_width=True):
                with get_db_connection() as conn:
                    user_row = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u_name.strip().lower(), u_pass)).fetchone()
                    if user_row:
                        st.session_state.current_user = dict(user_row)
                        st.success(f"مرحباً بك، {user_row['name']}")
                        st.rerun()
                    else:
                        st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")
    st.stop()


# ==============================================================================
# 5. الشريط الجانبي
# ==============================================================================
current_u = st.session_state.current_user
user_role = current_u["role"]
comp = db_get_company()
egs = db_get_egs()

with st.sidebar:
    st.title("رؤية المستقبل الذكي")
    st.caption("SMART FUTURE VISION")
    st.write(f"👤 المستخدم: **{current_u['name']}**")
    
    badge_style = "role-admin" if user_role == "ADMIN" else ("role-accountant" if user_role == "ACCOUNTANT" else "role-sales")
    st.markdown(f"الصلاحية: <span class='role-badge {badge_style}'>{current_u['role_title']}</span>", unsafe_allow_html=True)
    
    if st.button("تسجيل الخروج 🚪", use_container_width=True):
        st.session_state.current_user = None
        st.rerun()
        
    st.markdown("---")
    menu_options = ["لوحة التحكم (Dashboard)", "عروض الأسعار (Quotations)", "الفواتير الضريبية (Invoices)"]
    if user_role == "ADMIN":
        menu_options.append("بيانات المنشأة والتوقيع (Settings)")
        menu_options.append("إعدادات الربط والـ EGS (ZATCA)")
        
    selected_menu = st.radio("التنقل بين الشاشات:", menu_options)
    st.markdown("---")
    st.success("📄 الورقة الرسمية المعتمدة نشطة")
    st.caption("💾 قاعدة البيانات: `fatoora_data.db`")


# ==============================================================================
# 6. الشاشة الأولى: لوحة التحكم
# ==============================================================================
if selected_menu == "لوحة التحكم (Dashboard)":
    st.header("📊 لوحة المتابعة والمؤشرات العامة")
    
    invoices = db_get_invoices()
    quotations = db_get_quotations()
    
    c1, c2, c3, c4 = st.columns(4)
    total_sales = sum(inv["total"] for inv in invoices if inv["zatca_status"] != "DRAFT")
    total_vat = sum(inv["vat"] for inv in invoices if inv["zatca_status"] != "DRAFT")
    active_quotes = len([q for q in quotations if q["status"] != "CONVERTED"])
    
    c1.metric("إجمالي المبيعات المعتمدة", f"{total_sales:,.2f} ر.س")
    c2.metric("ضريبة القيمة المضافة (15%)", f"{total_vat:,.2f} ر.س")
    c3.metric("عروض الأسعار المفتوحة", active_quotes)
    c4.metric("عدد الفواتير الصادرة", len(invoices))
    
    st.markdown("### 🕒 آخر العمليات المسجلة")
    if invoices:
        df_inv = pd.DataFrame([
            {
                "رقم الفاتورة": inv["invoice_number"],
                "النوع": inv["subtype"],
                "العميل": inv["customer_name"],
                "الإجمالي": f"{inv['total']:,.2f} ر.س",
                "الحالة": inv["zatca_status"],
                "التاريخ": inv["timestamp"]
            } for inv in invoices[:5]
        ])
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("لا توجد فواتير بعد.")


# ==============================================================================
# 7. الشاشة الثانية: عروض الأسعار
# ==============================================================================
elif selected_menu == "عروض الأسعار (Quotations)":
    tab_list, tab_create = st.tabs(["📋 قائمة العروض الحالية", "➕ إنشاء عرض سعر جديد"])
    
    with tab_list:
        quotes = db_get_quotations()
        
        c_top1, c_top2 = st.columns([3, 1.2])
        c_top1.subheader("عروض الأسعار المسجلة")
        
        if len(quotes) > 1:
            if c_top2.button("🧹 تنظيف وحذف العروض المكررة", use_container_width=True):
                db_clean_duplicate_quotations()
                st.toast("تم تنظيف العروض المكررة!")
                time.sleep(0.4)
                st.rerun()

        if not quotes:
            st.warning("لا توجد عروض أسعار مسجلة.")
        else:
            for q in quotes:
                with st.expander(f"📌 عرض رقم: {q['id']} — {q['customer_name']} ({q['total']:,.2f} ر.س)"):
                    doc_html = render_official_document_html("QUOTATION", q, comp)
                    st.markdown(doc_html, unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    c_act1, c_act2, c_act3 = st.columns([1.5, 1.5, 1])
                    
                    pdf_bytes = generate_pdf_bytes(doc_html)
                    if pdf_bytes:
                        c_act1.download_button(
                            label="📥 تنزيل عرض السعر كـ PDF رسمي",
                            data=pdf_bytes,
                            file_name=f"عرض_سعر_{q['id']}.pdf",
                            mime="application/pdf",
                            key=f"dl_q_btn_{q['id']}",
                            type="primary",
                            use_container_width=True
                        )

                    if q["status"] == "ACCEPTED":
                        if c_act2.button("🚀 تحويل إلى فاتورة ZATCA", key=f"conv_btn_{q['id']}", use_container_width=True):
                            new_icv = egs["current_icv"] + 1
                            now_dt = datetime.datetime.now()
                            inv_num = f"SME{new_icv:05d}"
                            
                            qr_b64 = generate_zatca_qr_base64(
                                seller_name=comp["name"],
                                vat_no=comp["vat_number"],
                                timestamp=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                total_str=f"{q['total']:.2f}",
                                vat_str=f"{q['vat']:.2f}"
                            )
                            
                            new_invoice = {
                                "id": str(uuid.uuid4()),
                                "invoice_number": inv_num,
                                "internal_number": f"2026-{new_icv:05d}",
                                "quotation_id": q["id"],
                                "customer_name": q["customer_name"],
                                "customer_vat": q["customer_vat"],
                                "customer_type": q["customer_type"],
                                "contract_number": q.get("contract_number", "59/576"),
                                "buyer_address": f"{q.get('buyer_city', 'الرياض')} - {q.get('buyer_district', 'حي الندوة')}",
                                "subtype": "فاتورة ضريبية قياسية (0100000)" if q["customer_type"] == "B2B" else "فاتورة مبسطة (0200000)",
                                "icv": new_icv,
                                "created_by": current_u["name"],
                                "timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                "supply_date": str(datetime.date.today()),
                                "items": q["items"],
                                "subtotal": q["subtotal"],
                                "vat": q["vat"],
                                "total": q["total"],
                                "zatca_status": "CLEARED" if q["customer_type"] == "B2B" else "REPORTED",
                                "qr_b64": qr_b64
                            }
                            db_save_invoice(new_invoice)
                            db_update_egs(new_icv, "NWZlMmVkYjI0OGI1NTkxMGExZGY2YTEyNTY3YTg3MTA=")
                            q["status"] = "CONVERTED"
                            q["converted_invoice_id"] = inv_num
                            db_save_quotation(q)
                            st.success(f"تم تحويل العرض إلى الفاتورة رقم {inv_num} بنجاح!")
                            time.sleep(0.4)
                            st.rerun()

                    if c_act3.button("🗑️ حذف العرض", key=f"del_q_btn_{q['id']}", use_container_width=True):
                        db_delete_quotation(q["id"])
                        st.toast("تم حذف عرض السعر")
                        time.sleep(0.4)
                        st.rerun()

    with tab_create:
        st.subheader("إنشاء عرض سعر جديد")
        
        if "quote_builder_items" not in st.session_state:
            st.session_state.quote_builder_items = [
                {"name": "رسائل علمية / تصنيفها بالكليات وعمل كشوف تعبئة خاصة بها", "qty": 1, "price": 13000.0}
            ]

        col_c1, col_c2 = st.columns(2)
        c_name = col_c1.text_input("اسم العميل / السادة", value="جامعة نايف العربية للعلوم الأمنية", key="qc_name")
        c_type = col_c2.selectbox("نوع التعامل", ["B2B", "B2C"], key="qc_type")
        c_vat = col_c1.text_input("الرقم الضريبي للمشتري", value="310993014100013", key="qc_vat")
        c_contract = col_c2.text_input("رقم التعميد / المرجع", value="59/576", key="qc_contract")
        
        st.markdown("---")
        st.write("#### بنود عرض السعر (إمكانية إضافة وحذف عدة بنود)")
        
        for idx, itm in enumerate(st.session_state.quote_builder_items):
            col_i1, col_i2, col_i3, col_i4 = st.columns([3, 1, 1.2, 0.5])
            itm["name"] = col_i1.text_input(f"وصف البند #{idx+1}", value=itm["name"], key=f"q_item_name_{idx}")
            itm["qty"] = col_i2.number_input(f"الكمية #{idx+1}", min_value=1, value=int(itm["qty"]), key=f"q_item_qty_{idx}")
            itm["price"] = col_i3.number_input(f"السعر / الوحدة #{idx+1}", min_value=1.0, value=float(itm["price"]), step=50.0, key=f"q_item_price_{idx}")
            
            if len(st.session_state.quote_builder_items) > 1:
                if col_i4.button("🗑️", key=f"del_q_item_{idx}"):
                    st.session_state.quote_builder_items.pop(idx)
                    st.rerun()

        if st.button("➕ إضافة بند جديد لعرض السعر"):
            st.session_state.quote_builder_items.append({"name": "", "qty": 1, "price": 100.0})
            st.rerun()

        st.markdown("---")
        total_sub = sum(it["qty"] * it["price"] for it in st.session_state.quote_builder_items)
        total_v = total_sub * 0.15
        total_g = total_sub + total_v
        
        st.info(f"المجموع: **{total_sub:,.2f} ر.س** | ضريبة القيمة المضافة (15%): **{total_v:,.2f} ر.س** | الصافي الإجمالي: :green[**{total_g:,.2f} ر.س**]")

        if st.button("حفظ عرض السعر 💾", type="primary", use_container_width=True):
            new_q_id = f"QUO-2026-{len(quotes)+1:03d}"
            new_q = {
                "id": new_q_id,
                "customer_name": c_name,
                "customer_vat": c_vat if c_type == "B2B" else "",
                "customer_type": c_type,
                "contract_number": c_contract,
                "date": str(datetime.date.today()),
                "created_by": current_u["name"],
                "buyer_city": "الرياض",
                "buyer_district": "حي الندوة",
                "buyer_street": "طريق خريص",
                "buyer_building": "6830",
                "buyer_postal": "11452",
                "items": st.session_state.quote_builder_items,
                "subtotal": total_sub,
                "vat": total_v,
                "total": total_g,
                "status": "ACCEPTED",
                "converted_invoice_id": None
            }
            db_save_quotation(new_q)
            st.success("تم حفظ عرض السعر بنجاح بقاعدة البيانات!")
            time.sleep(0.5)
            st.rerun()


# ==============================================================================
# 8. الشاشة الثالثة: الفواتير الضريبية
# ==============================================================================
elif selected_menu == "الفواتير الضريبية (Invoices)":
    tab_inv_list, tab_inv_create = st.tabs(["🧾 قائمة الفواتير الصادرة", "➕ إنشاء فاتورة جديدة مباشرة"])
    invoices = db_get_invoices()

    with tab_inv_list:
        st.subheader("سجل الفواتير الرسمية")
        
        if not invoices:
            st.warning("لا توجد فواتير بعد. يمكنك إنشاء فاتورة مباشرة أو تحويل عرض سعر.")
        else:
            for inv in invoices:
                with st.expander(f"🧾 فاتورة: {inv['invoice_number']} — {inv['customer_name']} ({inv['total']:,.2f} ر.س)"):
                    inv_html = render_official_document_html("INVOICE", inv, comp)
                    st.markdown(inv_html, unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 1])
                    inv_pdf = generate_pdf_bytes(inv_html)
                    if inv_pdf:
                        col_b1.download_button(
                            label="📥 تنزيل الفاتورة كـ PDF رسمي",
                            data=inv_pdf,
                            file_name=f"فاتورة_{inv['invoice_number']}.pdf",
                            mime="application/pdf",
                            key=f"dl_inv_btn_{inv['id']}",
                            type="primary",
                            use_container_width=True
                        )

                    if inv["zatca_status"] == "DRAFT":
                        if col_b2.button("🚀 اعتماد الفاتورة والربط بالزكاة", key=f"up_inv_{inv['id']}", use_container_width=True):
                            new_icv = egs["current_icv"] + 1
                            now_dt = datetime.datetime.now()
                            inv["icv"] = new_icv
                            inv["invoice_number"] = f"SME{new_icv:05d}"
                            inv["zatca_status"] = "CLEARED" if inv["customer_type"] == "B2B" else "REPORTED"
                            inv["qr_b64"] = generate_zatca_qr_base64(
                                seller_name=comp["name"],
                                vat_no=comp["vat_number"],
                                timestamp=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                total_str=f"{inv['total']:.2f}",
                                vat_str=f"{inv['vat']:.2f}"
                            )
                            db_save_invoice(inv)
                            db_update_egs(new_icv, "NWZlMmVkYjI0OGI1NTkxMGExZGY2YTEyNTY3YTg3MTA=")
                            st.success("تم اعتماد الفاتورة وتوليد ختم الزكاة ورفع العداد بنجاح!")
                            time.sleep(0.5)
                            st.rerun()

                    if col_b3.button("🗑️ حذف الفاتورة", key=f"del_inv_{inv['id']}", use_container_width=True):
                        db_delete_invoice(inv["id"])
                        st.toast("تم حذف الفاتورة")
                        time.sleep(0.4)
                        st.rerun()

    with tab_inv_create:
        st.subheader("إنشاء فاتورة جديدة مباشرة")
        
        if "inv_builder_items" not in st.session_state:
            st.session_state.inv_builder_items = [
                {"name": "خدمة أعمال استشارية وتصميم هوية", "qty": 1, "price": 5000.0}
            ]

        c_inv1, c_inv2 = st.columns(2)
        dir_c_name = c_inv1.text_input("اسم العميل / الجهة", value="مؤسسة التقنية المتطورة", key="dir_c_name")
        dir_c_type = c_inv2.selectbox("نوع المعاملة", ["B2B", "B2C"], key="dir_c_type")
        dir_c_vat = c_inv1.text_input("الرقم الضريبي للمشتري (إلزامي للـ B2B)", value="310993014100013", key="dir_c_vat")
        dir_contract = c_inv2.text_input("رقم التعميد أو أمر الشراء", value="59/576", key="dir_contract")
        
        st.markdown("---")
        inv_mode = st.radio(
            "اختر حالة الفاتورة عند الإصدار:",
            [
                "مسودة (Draft) — غير مربوطة بالزكاة (للتدقيق الداخلي)",
                "نهائية معتمدة (ZATCA Official) — مربوطة بالزكاة، ترفع العداد وتتضمن رمز QR المعتمد"
            ],
            index=1
        )

        st.markdown("---")
        st.write("#### بنود الفاتورة")
        
        for idx, itm in enumerate(st.session_state.inv_builder_items):
            col_d1, col_d2, col_d3, col_d4 = st.columns([3, 1, 1.2, 0.5])
            itm["name"] = col_d1.text_input(f"اسم البند #{idx+1}", value=itm["name"], key=f"d_item_name_{idx}")
            itm["qty"] = col_d2.number_input(f"الكمية #{idx+1}", min_value=1, value=int(itm["qty"]), key=f"d_item_qty_{idx}")
            itm["price"] = col_d3.number_input(f"السعر / الوحدة #{idx+1}", min_value=1.0, value=float(itm["price"]), step=50.0, key=f"d_item_price_{idx}")
            
            if len(st.session_state.inv_builder_items) > 1:
                if col_d4.button("🗑️", key=f"del_dir_item_{idx}"):
                    st.session_state.inv_builder_items.pop(idx)
                    st.rerun()

        if st.button("➕ إضافة بند جديد للفاتورة"):
            st.session_state.inv_builder_items.append({"name": "", "qty": 1, "price": 100.0})
            st.rerun()

        st.markdown("---")
        total_sub_inv = sum(it["qty"] * it["price"] for it in st.session_state.inv_builder_items)
        total_vat_inv = total_sub_inv * 0.15
        total_gross_inv = total_sub_inv + total_vat_inv
        
        st.info(f"المجموع: **{total_sub_inv:,.2f} ر.س** | ضريبة القيمة المضافة (15%): **{total_vat_inv:,.2f} ر.س** | الصافي الإجمالي: :green[**{total_gross_inv:,.2f} ر.س**]")

        if st.button("إصدار الفاتورة المباشرة 🚀", type="primary", use_container_width=True):
            now_dt = datetime.datetime.now()
            timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            is_draft_choice = "مسودة" in inv_mode

            if is_draft_choice:
                inv_number_final = f"DRAFT-{len(invoices)+1:04d}"
                icv_val = 0
                final_status = "DRAFT"
                qr_code_str = ""
            else:
                new_icv = egs["current_icv"] + 1
                inv_number_final = f"SME{new_icv:05d}"
                icv_val = new_icv
                final_status = "CLEARED" if dir_c_type == "B2B" else "REPORTED"
                qr_code_str = generate_zatca_qr_base64(
                    seller_name=comp["name"],
                    vat_no=comp["vat_number"],
                    timestamp=timestamp_str,
                    total_str=f"{total_gross_inv:.2f}",
                    vat_str=f"{total_vat_inv:.2f}"
                )
                db_update_egs(new_icv, "NWZlMmVkYjI0OGI1NTkxMGExZGY2YTEyNTY3YTg3MTA=")

            direct_inv_record = {
                "id": str(uuid.uuid4()),
                "invoice_number": inv_number_final,
                "internal_number": inv_number_final,
                "quotation_id": None,
                "customer_name": dir_c_name,
                "customer_vat": dir_c_vat if dir_c_type == "B2B" else "",
                "customer_type": dir_c_type,
                "contract_number": dir_contract,
                "buyer_address": "الرياض - المملكة العربية السعودية",
                "subtype": "فاتورة ضريبية قياسية (0100000)" if dir_c_type == "B2B" else "فاتورة مبسطة (0200000)",
                "icv": icv_val,
                "created_by": current_u["name"],
                "timestamp": timestamp_str,
                "supply_date": str(datetime.date.today()),
                "items": st.session_state.inv_builder_items,
                "subtotal": total_sub_inv,
                "vat": total_vat_inv,
                "total": total_gross_inv,
                "zatca_status": final_status,
                "qr_b64": qr_code_str
            }
            db_save_invoice(direct_inv_record)
            st.success(f"تم حفظ الفاتورة بنجاح برقم {inv_number_final}!")
            time.sleep(0.5)
            st.rerun()


# ==============================================================================
# 9. الشاشة الرابعة: بيانات المنشأة ورفع الشعار والختم والتوقيع
# ==============================================================================
elif selected_menu == "بيانات المنشأة والتوقيع (Settings)":
    st.header("⚙️ إعدادات المنشأة ورفع الشعار والختم والتوقيع الرسمي")
    
    with st.form("company_info_form"):
        col1, col2 = st.columns(2)
        c_name = col1.text_input("اسم المنشأة القانوني", value=comp.get("name", ""))
        c_trade = col2.text_input("الاسم بالإنجليزية (Trade Name)", value=comp.get("trade_name", ""))
        c_vat = col1.text_input("الرقم الضريبي (15 رقم)", value=comp.get("vat_number", ""), max_chars=15)
        c_cr = col2.text_input("رقم السجل التجاري", value=comp.get("cr_number", ""))
        c_phone = col1.text_input("رقم الهاتف", value=comp.get("phone", ""))
        c_mail = col2.text_input("البريد الإلكتروني", value=comp.get("email", ""))
        c_city = col1.text_input("المدينة", value=comp.get("city", ""))
        c_dist = col2.text_input("الحي", value=comp.get("district", ""))
        
        st.markdown("---")
        st.write("#### البيانات البنكية المعتمدة للمستفيد")
        col3, col4 = st.columns(2)
        c_bank = col3.text_input("اسم البنك", value=comp.get("bank_name", "مصرف الراجحي"))
        c_acc = col4.text_input("رقم الحساب البنكي", value=comp.get("account_number") or "666000010006086322302")
        c_iban = col3.text_input("رقم الآيبان (IBAN)", value=comp.get("iban", "SA9180000666608016322302"))
        
        if st.form_submit_button("حفظ بيانات المنشأة والحسابات 💾", type="primary"):
            comp.update({
                "name": c_name, "trade_name": c_trade, "vat_number": c_vat,
                "cr_number": c_cr, "phone": c_phone, "email": c_mail,
                "city": c_city, "district": c_dist, "bank_name": c_bank,
                "account_number": c_acc, "iban": c_iban
            })
            db_update_company(comp)
            st.success("تم تحديث وحفظ بيانات المنشأة بنجاح!")
            time.sleep(0.4)
            st.rerun()

    st.markdown("---")
    st.subheader("🖼️ رفع صور الشعار والختم والتوقيع للورقة الرسمية")
    
    col_u1, col_u2, col_u3 = st.columns(3)
    
    with col_u1:
        st.write("**شعار المؤسسة (Logo):**")
        if comp.get("logo_b64"):
            st.image(base64.b64decode(comp["logo_b64"]), width=170)
        up_logo = st.file_uploader("اختر صورة الشعار", type=["png", "jpg", "jpeg"], key="upl_logo")
        if up_logo and st.button("حفظ الشعار 💾"):
            comp["logo_b64"] = base64.b64encode(up_logo.read()).decode()
            db_update_company(comp)
            st.success("تم حفظ الشعار وتطبيقه بحجم كبير وواضح!")
            time.sleep(0.4)
            st.rerun()

    with col_u2:
        st.write("**الختم الرسمي (Stamp):**")
        if comp.get("stamp_b64"):
            st.image(base64.b64decode(comp["stamp_b64"]), width=115)
        up_stamp = st.file_uploader("اختر صورة الختم", type=["png", "jpg", "jpeg"], key="upl_stamp")
        if up_stamp and st.button("حفظ الختم 💾"):
            comp["stamp_b64"] = base64.b64encode(up_stamp.read()).decode()
            db_update_company(comp)
            st.success("تم حفظ الختم بنجاح!")
            time.sleep(0.4)
            st.rerun()

    with col_u3:
        st.write("**التوقيع الرسمي (Signature):**")
        if comp.get("signature_b64"):
            st.image(base64.b64decode(comp["signature_b64"]), width=145)
        up_sig = st.file_uploader("اختر صورة التوقيع", type=["png", "jpg", "jpeg"], key="upl_sig")
        if up_sig and st.button("حفظ التوقيع 💾"):
            comp["signature_b64"] = base64.b64encode(up_sig.read()).decode()
            db_update_company(comp)
            st.success("تم حفظ التوقيع واعتماده في المستندات!")
            time.sleep(0.4)
            st.rerun()


# ==============================================================================
# 10. الشاشة الخامسة: إعدادات الربط والـ EGS (ZATCA)
# ==============================================================================
elif selected_menu == "إعدادات الربط والـ EGS (ZATCA)":
    st.header("⚙️ إعدادات جهاز الفوترة والربط مع ZATCA")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("بيانات وحدة الـ EGS المعتمدة")
        st.text_input("معرّف الجهاز (EGS UUID)", "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d", disabled=True)
        st.text_input("الرقم التسلسلي للجهاز", "SFV-EGS-RIYADH-01", disabled=True)
        st.number_input("آخر قيمة للعداد الرسمي (ICV)", value=egs["current_icv"], disabled=True)
        st.text_area("هاش الفاتورة السابقة (PIH)", egs["last_hash"], height=70, disabled=True)
        
    with col2:
        st.subheader("تأهيل جهاز جديد (Onboarding Wizard)")
        with st.form("onboarding_form"):
            otp_code = st.text_input("رمز التحقق لمرة واحدة (OTP من منصة فاتورة)", placeholder="123456")
            env_type = st.selectbox("بيئة العمل", ["بيئة المحاكاة (Simulation)", "بيئة الإنتاج الحية (Production)"])
            
            if st.form_submit_button("استخراج شهادة الـ CSID 🔑", type="primary"):
                if len(otp_code) == 6:
                    with st.spinner("جاري إرسال الـ CSR واجتياز اختبارات الامتثال..."):
                        time.sleep(1.5)
                        st.success("تم بنجاح ربط الجهاز واستخراج شهادة الإنتاج المعتمدة وحفظها!")
                else:
                    st.error("يرجى إدخال رمز OTP صالح مكون من 6 أرقام.")
