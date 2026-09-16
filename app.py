import streamlit as st
import sqlite3
import json
import os
import io
import base64
import qrcode
from datetime import datetime, date

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="نظام الفواتير وعروض الأسعار | مؤسسة رؤية المستقبل الذكي",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- إعداد قاعدة البيانات ---
DB_FILE = "fatoora_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # جدول بيانات المؤسسة
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS company (
            id INTEGER PRIMARY KEY,
            name_en TEXT,
            name_ar TEXT,
            tax_number TEXT,
            cr_number TEXT,
            phone TEXT,
            email TEXT,
            bank_account TEXT,
            bank_name TEXT,
            iban TEXT,
            address_city TEXT,
            address_district TEXT,
            address_street TEXT,
            address_postal_code TEXT,
            address_building_no TEXT,
            logo_path TEXT,
            stamp_path TEXT,
            signature_path TEXT
        )""")
        
        # جدول المستخدمين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            full_name TEXT,
            role TEXT,
            job_title TEXT
        )""")
        
        # جدول عروض الأسعار
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            quote_number TEXT PRIMARY KEY,
            client_tax_number TEXT,
            client_name TEXT,
            client_type TEXT,
            national_address TEXT,
            city TEXT,
            district TEXT,
            street TEXT,
            postal_code TEXT,
            building_no TEXT,
            quote_date TEXT,
            expiry_date TEXT,
            items TEXT,
            subtotal REAL,
            vat_amount REAL,
            total REAL,
            status TEXT,
            notes TEXT
        )""")

        # جدول الفواتير
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_number TEXT PRIMARY KEY,
            quote_number TEXT,
            client_tax_number TEXT,
            client_name TEXT,
            client_type TEXT,
            national_address TEXT,
            city TEXT,
            district TEXT,
            street TEXT,
            postal_code TEXT,
            building_no TEXT,
            invoice_date TEXT,
            supply_date TEXT,
            items TEXT,
            subtotal REAL,
            vat_amount REAL,
            total REAL,
            status TEXT,
            notes TEXT,
            qr_code TEXT
        )""")

        # جدول ربط الزكاة (EGS)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS egs_config (
            id INTEGER PRIMARY KEY,
            is_active INTEGER,
            csr TEXT,
            is_production INTEGER,
            csid_token TEXT
        )""")

        # إدخال بيانات المؤسسة الافتراضية
        cursor.execute("SELECT COUNT(*) FROM company")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO company VALUES (
                1, 'SMART FUTURE VISION', 'مؤسسة رؤية المستقبل الذكي',
                '312731823400003', '1009160447', '0560095895',
                'info@sfv-sa.com', '666000010006086322302', 'مصرف الراجحي',
                'SA918000066608016322302', 'الرياض', 'حي النظيم',
                'شارع الصلاح', '14816', '7966', '', '', ''
            )""")

        # إدخال وتحديث بيانات المستخدمين بكلمة المرور الجديدة Smart@2026
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users VALUES ('admin', 'Smart@2026', 'المدير العام', 'ADMIN', 'مدير النظام')")
            cursor.execute("INSERT INTO users VALUES ('sales', 'Smart@2026', 'مسؤول المبيعات', 'SALES', 'مسؤول مبيعات')")
            cursor.execute("INSERT INTO users VALUES ('accountant', 'Smart@2026', 'المحاسب المالي', 'ACCOUNTANT', 'محاسب')")
        else:
            cursor.execute("UPDATE users SET password = 'Smart@2026'")

        conn.commit()

init_database()

# --- دوال المساعدة للبيانات ---
def get_company():
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM company WHERE id=1").fetchone()
        return dict(row) if row else {}

def update_company(data):
    with get_db_connection() as conn:
        conn.execute("""
        UPDATE company SET
            name_en = :name_en, name_ar = :name_ar, tax_number = :tax_number,
            cr_number = :cr_number, phone = :phone, email = :email,
            bank_account = :bank_account, bank_name = :bank_name, iban = :iban,
            address_city = :address_city, address_district = :address_district,
            address_street = :address_street, address_postal_code = :address_postal_code,
            address_building_no = :address_building_no
        WHERE id=1
        """, data)
        conn.commit()

# --- تشفير رمز الاستجابة السريعة (ZATCA TLV QR) ---
def get_tlv_tag(tag_num, tag_value):
    tag_bytes = tag_value.encode('utf-8')
    return bytes([tag_num, len(tag_bytes)]) + tag_bytes

def generate_zatca_qr(seller_name, vat_no, timestamp, total_amount, vat_amount):
    tlv = (
        get_tlv_tag(1, seller_name) +
        get_tlv_tag(2, vat_no) +
        get_tlv_tag(3, timestamp) +
        get_tlv_tag(4, str(total_amount)) +
        get_tlv_tag(5, str(vat_amount))
    )
    b64_qr = base64.b64encode(tlv).decode('utf-8')
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(b64_qr)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- توليد قالب A4 الرسمي للطباعة والتصدير ---
def render_official_doc(doc_type, doc_number, doc_date, expiry_or_supply_date, client_data, items, subtotal, vat_amount, total, company_info, qr_b64=None):
    items_rows = ""
    for idx, item in enumerate(items, start=1):
        price = float(item.get('price', 0.0))
        qty = int(item.get('qty', 1))
        row_vat = price * qty * 0.15
        row_total = (price * qty) + row_vat
        items_rows += f"""
        <tr>
            <td style="text-align: center; font-weight: bold; border: 1px solid #000; padding: 8px;">{idx}</td>
            <td style="border: 1px solid #000; padding: 8px; font-weight: bold;">{item.get('name', '')}</td>
            <td style="text-align: center; border: 1px solid #000; padding: 8px;">{qty}</td>
            <td style="text-align: center; border: 1px solid #000; padding: 8px;">{price:,.2f}</td>
            <td style="text-align: center; border: 1px solid #000; padding: 8px;">15%</td>
            <td style="text-align: center; border: 1px solid #000; padding: 8px;">{row_vat:,.2f}</td>
            <td style="text-align: center; font-weight: bold; border: 1px solid #000; padding: 8px;">{row_total:,.2f}</td>
        </tr>
        """

    title_ar = "فاتورة ضريبية" if doc_type == "INVOICE" else "عرض أسعار"
    date_label = "تاريخ التوريد" if doc_type == "INVOICE" else "تاريخ الانتهاء"

    qr_html = ""
    if qr_b64:
        qr_html = f'<img src="data:image/png;base64,{qr_b64}" style="width: 110px; height: 110px; border: 1px solid #ddd; padding: 4px; border-radius: 4px;" />'

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 10mm;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 10px;
                color: #000;
                background-color: #fff;
            }}
            .no-print {{
                display: block;
                text-align: center;
                margin-bottom: 20px;
            }}
            @media print {{
                .no-print {{
                    display: none !important;
                }}
                body {{
                    padding: 0;
                }}
            }}
            .a4-container {{
                width: 100%;
                max-width: 850px;
                margin: 0 auto;
                background: #fff;
                padding: 15px;
                box-sizing: border-box;
            }}
            .header-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            .doc-title-box {{
                text-align: center;
                border: 2px solid #107c41;
                background-color: #f4fbf7;
                padding: 6px;
                border-radius: 6px;
                font-size: 20px;
                font-weight: bold;
                color: #107c41;
                margin-bottom: 15px;
            }}
            .info-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
                font-size: 13px;
            }}
            .info-table td {{
                border: 1px solid #bbb;
                padding: 6px 10px;
            }}
            .items-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
                font-size: 13px;
            }}
            .items-table th {{
                background-color: #f1f1f1;
                border: 1px solid #000;
                padding: 8px;
                font-weight: bold;
            }}
            .bank-box {{
                border: 1.5px solid #000;
                padding: 10px 14px;
                border-radius: 4px;
                font-size: 12.5px;
                line-height: 1.6;
                width: 58%;
                float: right;
            }}
            .stamp-box {{
                width: 38%;
                float: left;
                text-align: center;
            }}
            .stamp-circle {{
                display: inline-block;
                border: 3px double #1a365d;
                border-radius: 50%;
                width: 125px;
                height: 125px;
                color: #1a365d;
                text-align: center;
                vertical-align: middle;
                padding-top: 15px;
                box-sizing: border-box;
                font-size: 10.5px;
                font-weight: bold;
            }}
            .signature-blue {{
                font-family: 'Brush Script MT', cursive, sans-serif;
                color: #0d47a1;
                font-size: 32px;
                transform: rotate(-8deg);
                margin-top: 5px;
                font-weight: bold;
            }}
            .footer-line {{
                border-top: 2px solid #000;
                margin-top: 25px;
                padding-top: 8px;
                text-align: center;
                font-size: 12px;
                clear: both;
            }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <button onclick="window.print()" style="
                background-color: #107c41;
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
                cursor: pointer;
                box-shadow: 0 4px 6px rgba(0,0,0,0.15);
            ">
                🖨️ طباعة / حفظ المستند كـ PDF الآن
            </button>
        </div>

        <div class="a4-container">
            <!-- رأس الصفحة -->
            <table class="header-table">
                <tr>
                    <td style="width: 35%; vertical-align: top; text-align: right;">
                        <h2 style="margin: 0; color: #107c41; font-size: 18px;">{company_info.get('name_ar', '')}</h2>
                        <div style="font-size: 12px; font-weight: bold; margin-top: 4px;">{company_info.get('name_en', '')}</div>
                        <div style="font-size: 12px; margin-top: 2px;">السجل التجاري: {company_info.get('cr_number', '')}</div>
                        <div style="font-size: 12px;">الرقم الضريبي: {company_info.get('tax_number', '')}</div>
                    </td>
                    <td style="width: 30%; text-align: center; vertical-align: middle;">
                        {qr_html if qr_html else '<div style="font-size: 28px; font-weight: bold; color: #107c41;">SFV</div>'}
                    </td>
                    <td style="width: 35%; vertical-align: top; text-align: left; font-size: 12px; line-height: 1.6;">
                        <div><strong>رقم المستند:</strong> {doc_number}</div>
                        <div><strong>تاريخ الإصدار:</strong> {doc_date}</div>
                        <div><strong>{date_label}:</strong> {expiry_or_supply_date}</div>
                    </td>
                </tr>
            </table>

            <div class="doc-title-box">
                {title_ar} - {doc_number}
            </div>

            <!-- جدول بيانات العميل -->
            <table class="info-table">
                <tr>
                    <td style="background-color: #fafafa; width: 18%;"><strong>اسم العميل:</strong></td>
                    <td style="font-weight: bold;">{client_data.get('name', '')}</td>
                    <td style="background-color: #fafafa; width: 18%;"><strong>الرقم الضريبي:</strong></td>
                    <td>{client_data.get('tax_no', 'غير متوفر')}</td>
                </tr>
                <tr>
                    <td style="background-color: #fafafa;"><strong>العنوان الوطني:</strong></td>
                    <td>{client_data.get('address', '')}</td>
                    <td style="background-color: #fafafa;"><strong>نوع التعامل:</strong></td>
                    <td>{client_data.get('type', 'B2B - منشآت')}</td>
                </tr>
            </table>

            <!-- جدول البنود -->
            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 5%;">م</th>
                        <th style="width: 45%;">البيان / الوصف</th>
                        <th style="width: 8%;">الكمية</th>
                        <th style="width: 12%;">السعر</th>
                        <th style="width: 8%;">الضريبة</th>
                        <th style="width: 10%;">قيمة الضريبة</th>
                        <th style="width: 12%;">المجموع</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                    <tr style="background-color: #fbfbfb; font-weight: bold;">
                        <td colspan="2" style="text-align: center; font-size: 15px; border: 1px solid #000; padding: 10px;">المجموع الكلي</td>
                        <td style="text-align: center; border: 1px solid #000;">{sum([int(i.get('qty', 1)) for i in items])}</td>
                        <td style="text-align: center; border: 1px solid #000;">{subtotal:,.2f}</td>
                        <td style="text-align: center; border: 1px solid #000;">15%</td>
                        <td style="text-align: center; border: 1px solid #000;">{vat_amount:,.2f}</td>
                        <td style="text-align: center; font-size: 15px; border: 1px solid #000; padding: 10px; color: #107c41;">{total:,.2f} ر.س</td>
                    </tr>
                </tbody>
            </table>

            <!-- القسم السفلي: البنك والأختام -->
            <div style="margin-top: 15px; overflow: hidden;">
                <div class="bank-box">
                    <div style="font-weight: bold; text-decoration: underline; margin-bottom: 4px;">البيانات البنكية للمستفيد:</div>
                    <div><strong>اسم المستفيد:</strong> {company_info.get('name_ar', '')}</div>
                    <div><strong>اسم البنك:</strong> {company_info.get('bank_name', '')}</div>
                    <div><strong>رقم الحساب:</strong> {company_info.get('bank_account', '')}</div>
                    <div><strong>رقم الآيبان:</strong> {company_info.get('iban', '')}</div>
                </div>

                <div class="stamp-box">
                    <div style="font-weight: bold; margin-bottom: 5px;">التوقيع والاعتماد الرسمي:</div>
                    <div class="stamp-circle">
                        مؤسسة رؤية المستقبل الذكي<br>
                        س.ت {company_info.get('cr_number', '')}<br>
                        <span style="font-size: 13px; color: #c00;">★ معتمد ★</span><br>
                        Smart Future Vision
                    </div>
                    <div class="signature-blue">Sherif Magdi</div>
                </div>
            </div>

            <!-- ذيل الصفحة -->
            <div class="footer-line">
                <strong>{company_info.get('name_ar', '')}</strong> ، السجل التجاري: {company_info.get('cr_number', '')} | الرقم الضريبي: {company_info.get('tax_number', '')}<br>
                العنوان: {company_info.get('address_city', '')} - {company_info.get('address_district', '')} | هاتف: {company_info.get('phone', '')} | إيميل: {company_info.get('email', '')}
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

# --- إدارة حالة الجلسة وتسجيل الدخول ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None

def login_user(username, password):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        return dict(user) if user else None

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; color: #107c41;'>نظام الفواتير وعروض الأسعار</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>مؤسسة رؤية المستقبل الذكي</h4><br>", unsafe_allow_html=True)
    
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        with st.form("login_form"):
            uname = st.text_input("اسم المستخدم", placeholder="admin")
            upass = st.text_input("كلمة المرور", type="password", placeholder="Smart@2026")
            submit = st.form_submit_button("تسجيل الدخول", use_container_width=True)
            if submit:
                user = login_user(uname.strip(), upass.strip())
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success(f"مرحباً بك {user['full_name']}")
                    st.rerun()
                else:
                    st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# --- الشريط الجانبي والقائمة الرئيسية ---
comp = get_company()

st.sidebar.markdown(f"### 👤 {st.session_state.user['full_name']}")
st.sidebar.caption(f"الدور: {st.session_state.user['job_title']}")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "القائمة الرئيسية",
    ["📋 عروض الأسعار (Quotations)", "🧾 الفواتير الضريبية (Invoices)", "📊 أرشيف السجلات", "⚙️ إعدادات المؤسسة"]
)

if st.sidebar.button("تسجيل الخروج", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

# ==============================
# 1. شاشة عروض الأسعار
# ==============================
if menu == "📋 عروض الأسعار (Quotations)":
    st.title("📋 إدارة وتوليد عروض الأسعار")
    
    with st.expander("➕ إنشاء عرض سعر جديد", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            quote_num = st.text_input("رقم عرض السعر", value=f"QUO-{datetime.now().strftime('%Y%m')}-{os.urandom(2).hex().upper()}")
            client_name = st.text_input("اسم العميل / الجهة", value="جامعة نايف العربية للعلوم الأمنية")
        with col2:
            quote_date = st.date_input("تاريخ العرض", date.today())
            client_tax = st.text_input("الرقم الضريبي للعميل", value="310993014100013")
        with col3:
            expiry_date = st.date_input("صالح حتى تاريخ", date.today())
            client_addr = st.text_input("العنوان الوطني للعميل", value="الرياض - طريق خريص")

        st.markdown("##### 📦 بنود العرض")
        if 'quote_items' not in st.session_state:
            st.session_state.quote_items = [{"name": "خدمة أعمال استشارية وتقنية", "qty": 1, "price": 5000.0}]

        for idx, itm in enumerate(st.session_state.quote_items):
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.5, 0.5])
            with ic1:
                itm['name'] = st.text_input(f"وصف الخدمة #{idx+1}", value=itm['name'], key=f"q_name_{idx}")
            with ic2:
                itm['qty'] = st.number_input(f"الكمية #{idx+1}", min_value=1, value=int(itm['qty']), key=f"q_qty_{idx}")
            with ic3:
                itm['price'] = st.number_input(f"السعر الفردي #{idx+1}", min_value=0.0, value=float(itm['price']), step=100.0, key=f"q_price_{idx}")
            with ic4:
                if st.button("❌", key=f"del_q_{idx}") and len(st.session_state.quote_items) > 1:
                    st.session_state.quote_items.pop(idx)
                    st.rerun()

        if st.button("➕ إضافة بند جديد للعرض"):
            st.session_state.quote_items.append({"name": "", "qty": 1, "price": 0.0})
            st.rerun()

    # الحسابات
    subtotal = sum([float(i['price']) * int(i['qty']) for i in st.session_state.quote_items])
    vat = subtotal * 0.15
    total = subtotal + vat

    client_dict = {"name": client_name, "tax_no": client_tax, "address": client_addr, "type": "B2B"}
    html_quote = render_official_doc("QUOTE", quote_num, str(quote_date), str(expiry_date), client_dict, st.session_state.quote_items, subtotal, vat, total, comp)

    st.markdown("### 👁️ معاينة عرض السعر الرسمي (A4)")
    
    # أزرار التحميل المباشرة
    btn_c1, btn_c2 = st.columns([1, 2])
    with btn_c1:
        st.download_button(
            label="📥 حفظ ملف العرض للطباعة المباشرة (HTML)",
            data=html_quote,
            file_name=f"{quote_num}.html",
            mime="text/html",
            use_container_width=True
        )
    with btn_c2:
        if st.button("💾 حفظ عرض السعر في قاعدة البيانات", use_container_width=True):
            with get_db_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO quotations VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""", (
                    quote_num, client_tax, client_name, 'B2B', client_addr,
                    'الرياض', 'حي النظيم', 'شارع الصلاح', '14816', '7966',
                    str(quote_date), str(expiry_date), json.dumps(st.session_state.quote_items, ensure_ascii=False),
                    subtotal, vat, total, 'ISSUED', ''
                ))
                conn.commit()
            st.success("تم حفظ عرض السعر بنجاح في قاعدة البيانات!")

    st.components.v1.html(html_quote, height=850, scrolling=True)

# ==============================
# 2. شاشة الفواتير الضريبية
# ==============================
elif menu == "🧾 الفواتير الضريبية (Invoices)":
    st.title("🧾 إدارة وتوليد الفواتير الضريبية (ZATCA)")

    with st.expander("➕ إنشاء فاتورة جديدة", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            inv_num = st.text_input("رقم الفاتورة", value=f"INV-{datetime.now().strftime('%Y%m')}-{os.urandom(2).hex().upper()}")
            c_name = st.text_input("اسم العميل / المستلم", value="جامعة نايف العربية للعلوم الأمنية")
        with col2:
            inv_date = st.date_input("تاريخ الفاتورة", date.today())
            c_tax = st.text_input("الرقم الضريبي للعميل", value="310993014100013")
        with col3:
            supply_date = st.date_input("تاريخ التوريد", date.today())
            c_addr = st.text_input("العنوان الوطني", value="الرياض - طريق خريص")

        st.markdown("##### 📦 بنود الفاتورة")
        if 'inv_items' not in st.session_state:
            st.session_state.inv_items = [{"name": "خدمة أعمال استشارية وتقنية", "qty": 1, "price": 5000.0}]

        for idx, itm in enumerate(st.session_state.inv_items):
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.5, 0.5])
            with ic1:
                itm['name'] = st.text_input(f"الوصف #{idx+1}", value=itm['name'], key=f"inv_n_{idx}")
            with ic2:
                itm['qty'] = st.number_input(f"الكمية #{idx+1}", min_value=1, value=int(itm['qty']), key=f"inv_q_{idx}")
            with ic3:
                itm['price'] = st.number_input(f"السعر #{idx+1}", min_value=0.0, value=float(itm['price']), step=100.0, key=f"inv_p_{idx}")
            with ic4:
                if st.button("❌", key=f"del_inv_{idx}") and len(st.session_state.inv_items) > 1:
                    st.session_state.inv_items.pop(idx)
                    st.rerun()

        if st.button("➕ إضافة بند جديد للفاتورة"):
            st.session_state.inv_items.append({"name": "", "qty": 1, "price": 0.0})
            st.rerun()

    # الحسابات
    subtotal = sum([float(i['price']) * int(i['qty']) for i in st.session_state.inv_items])
    vat = subtotal * 0.15
    total = subtotal + vat

    # توليد رمز الاستجابة السريعة لهيئة الزكاة
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    qr_b64 = generate_zatca_qr(comp.get('name_ar', ''), comp.get('tax_number', ''), now_iso, f"{total:.2f}", f"{vat:.2f}")

    client_dict = {"name": c_name, "tax_no": c_tax, "address": c_addr, "type": "B2B"}
    html_invoice = render_official_doc("INVOICE", inv_num, str(inv_date), str(supply_date), client_dict, st.session_state.inv_items, subtotal, vat, total, comp, qr_b64=qr_b64)

    st.markdown("### 👁️ معاينة الفاتورة الضريبية الرسمية (A4)")
    
    # أزرار الحفظ والتحميل المتاحة دائماً
    col_save, col_dl = st.columns(2)
    with col_dl:
        st.download_button(
            label="📥 حفظ ملف الفاتورة للطباعة كـ PDF (HTML)",
            data=html_invoice,
            file_name=f"{inv_num}.html",
            mime="text/html",
            use_container_width=True
        )
    with col_save:
        if st.button("🚀 اعتماد الفاتورة والربط بالزكاة وحفظها", use_container_width=True):
            with get_db_connection() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO invoices VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""", (
                    inv_num, None, c_tax, c_name, 'B2B', c_addr,
                    'الرياض', 'حي النظيم', 'شارع الصلاح', '14816', '7966',
                    str(inv_date), str(supply_date), json.dumps(st.session_state.inv_items, ensure_ascii=False),
                    subtotal, vat, total, 'REPORTED', '', qr_b64
                ))
                conn.commit()
            st.success("تم اعتماد الفاتورة وتوليد رمز QR الزكاة بنجاح!")

    st.components.v1.html(html_invoice, height=850, scrolling=True)

# ==============================
# 3. شاشة السجلات والأرشيف
# ==============================
elif menu == "📊 أرشيف السجلات":
    st.title("📊 أرشيف الفواتير وعروض الأسعار")
    tab1, tab2 = st.tabs(["🧾 الفواتير المعتمدة", "📋 عروض الأسعار"])
    
    with tab1:
        with get_db_connection() as conn:
            invs = conn.execute("SELECT invoice_number, client_name, invoice_date, total, status FROM invoices ORDER BY rowid DESC").fetchall()
        if invs:
            for inv in invs:
                st.write(f"📄 **{inv['invoice_number']}** | {inv['client_name']} | {inv['invoice_date']} | المبلغ: **{inv['total']:,.2f} ر.س** | الحالة: `{inv['status']}`")
        else:
            st.info("لا توجد فواتير مسجلة حتى الآن.")

    with tab2:
        with get_db_connection() as conn:
            quos = conn.execute("SELECT quote_number, client_name, quote_date, total, status FROM quotations ORDER BY rowid DESC").fetchall()
        if quos:
            for q in quos:
                st.write(f"📑 **{q['quote_number']}** | {q['client_name']} | {q['quote_date']} | المبلغ: **{q['total']:,.2f} ر.س** | الحالة: `{q['status']}`")
        else:
            st.info("لا توجد عروض أسعار مسجلة.")

# ==============================
# 4. شاشة إعدادات المؤسسة
# ==============================
elif menu == "⚙️ إعدادات المؤسسة":
    st.title("⚙️ إعدادات وبيانات المنشأة والحسابات")
    with st.form("comp_form"):
        c1, c2 = st.columns(2)
        with c1:
            name_ar = st.text_input("اسم المؤسسة بالعربي", value=comp.get('name_ar', ''))
            name_en = st.text_input("اسم المؤسسة بالإنجليزي", value=comp.get('name_en', ''))
            cr = st.text_input("السجل التجاري", value=comp.get('cr_number', ''))
            tax = st.text_input("الرقم الضريبي (15 رقم)", value=comp.get('tax_number', ''))
            phone = st.text_input("رقم الهاتف / الجوال", value=comp.get('phone', ''))
            email = st.text_input("البريد الإلكتروني", value=comp.get('email', ''))
        with c2:
            bank_name = st.text_input("اسم البنك", value=comp.get('bank_name', ''))
            acc = st.text_input("رقم الحساب البنكي", value=comp.get('bank_account', ''))
            iban = st.text_input("رقم الآيبان (IBAN)", value=comp.get('iban', ''))
            city = st.text_input("المدينة", value=comp.get('address_city', ''))
            district = st.text_input("الحي", value=comp.get('address_district', ''))
            street = st.text_input("الشارع", value=comp.get('address_street', ''))

        if st.form_submit_button("حفظ التعديلات", use_container_width=True):
            update_company({
                "name_ar": name_ar, "name_en": name_en, "cr_number": cr, "tax_number": tax,
                "phone": phone, "email": email, "bank_name": bank_name, "bank_account": acc,
                "iban": iban, "address_city": city, "address_district": district,
                "address_street": street, "address_postal_code": comp.get('address_postal_code', '14816'),
                "address_building_no": comp.get('address_building_no', '7966')
            })
            st.success("تم تحديث وحفظ بيانات المؤسسة بنجاح!")
            st.rerun()
