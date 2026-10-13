from datetime import date, timedelta

import streamlit as st

from invoice_generator import (
    SUPPORTED_CURRENCIES,
    allocate_invoice_number,
    calculate_invoice_amounts,
    format_currency,
    generate_invoice_csv,
    generate_invoice_pdf,
    invoice_total_rows,
    validate_invoice_required_fields,
)
from exchange_rates import ExchangeRateError, convert_amount, fetch_exchange_rates
from invoice_history import get_invoice_record, list_invoice_history, save_invoice_record

PAYMENT_TERMS_DAYS = {
    "Due on receipt": 0,
    "Net 7 days": 7,
    "Net 15 days": 15,
    "Net 30 days": 30,
}
INVOICE_WIDGET_DEFAULTS = {
    "business_name": "",
    "customer_name": "",
    "invoice_number": "",
    "invoice_currency": "KES",
    "payment_terms": "Due on receipt",
    "discount_percent": 0.0,
    "tax_percent": 0.0,
    "business_address": "",
    "business_phone": "",
    "business_email": "",
    "business_tax_number": "",
    "business_mpesa_number": "",
    "payment_instructions": "",
    "customer_address": "",
    "customer_phone": "",
    "customer_email": "",
    "purchase_order": "",
    "product_name": "",
    "product_quantity": 1,
    "product_price": 1.0,
    "price_currency": "KES",
}


def preserve_invoice_draft():
    for key in INVOICE_WIDGET_DEFAULTS:
        if key in st.session_state:
            st.session_state[f"invoice_draft_{key}"] = st.session_state[key]
    uploaded_logo = st.session_state.get("business_logo")
    if uploaded_logo:
        st.session_state.invoice_draft_logo_bytes = uploaded_logo.getvalue()
        st.session_state.invoice_draft_logo_name = uploaded_logo.name


@st.cache_data(ttl=300, show_spinner=False)
def cached_exchange_rates(base_currency):
    return fetch_exchange_rates(base_currency)


def remove_product(index):
    st.session_state.products.pop(index)


def start_new_invoice():
    st.session_state.invoice_number = allocate_invoice_number()
    st.session_state.products.clear()


st.set_page_config(
    page_title="Invoice generator",
    page_icon=":material/receipt_long:",
    layout="wide",
)

if "products" not in st.session_state:
    st.session_state.products = []
if "invoice_number" not in st.session_state:
    st.session_state.invoice_number = st.session_state.get(
        "invoice_draft_invoice_number"
    ) or allocate_invoice_number()
else:
    allocate_invoice_number(existing_number=st.session_state.invoice_number)

st.title("Invoice generator", icon=":material/receipt_long:")
st.caption("Prepare and export a customer invoice.")

active_view = st.segmented_control(
    "Main navigation",
    options=["Create invoice", "Invoice history"],
    default="Create invoice",
    key="main_navigation",
    on_change=preserve_invoice_draft,
    label_visibility="collapsed",
    width="stretch",
)

if active_view == "Invoice history":
    st.subheader("Invoice history", icon=":material/history:")
    saved_invoices = list_invoice_history()
    if saved_invoices:
        st.dataframe(
            [
                {
                    "Invoice": invoice["invoice_number"],
                    "Date": invoice["invoice_date"],
                    "Business": invoice["business_name"],
                    "Customer": invoice["customer_name"],
                    "Currency": invoice["currency"],
                    "Total": invoice["total"],
                }
                for invoice in saved_invoices
            ],
            hide_index=True,
            alt="Saved invoice history",
        )
        history_number = st.selectbox(
            "Saved invoice",
            options=[invoice["invoice_number"] for invoice in saved_invoices],
            key="history_invoice_number",
        )
        selected_invoice = get_invoice_record(history_number)
        if selected_invoice:
            with st.container(horizontal=True, horizontal_alignment="right"):
                st.download_button(
                    "CSV",
                    data=selected_invoice["csv_content"],
                    file_name=f"invoice-{history_number}.csv",
                    mime="text/csv",
                    key=f"history_csv_{history_number}",
                    icon=":material/table_view:",
                )
                st.download_button(
                    "PDF",
                    data=selected_invoice["pdf_content"],
                    file_name=f"invoice-{history_number}.pdf",
                    mime="application/pdf",
                    key=f"history_pdf_{history_number}",
                    icon=":material/picture_as_pdf:",
                    type="primary",
                )
    else:
        st.caption("Saved invoices will appear here.")
    st.stop()

for key, default in INVOICE_WIDGET_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get(f"invoice_draft_{key}", default)

with st.container(border=True):
    invoice_heading, new_invoice_column = st.columns([5, 1], vertical_alignment="center")
    invoice_heading.subheader("Invoice details")
    new_invoice_column.button(
        "New invoice",
        on_click=start_new_invoice,
        icon=":material/add:",
        width="stretch",
    )
    business_column, customer_column, number_column, currency_column = st.columns(
        [2, 2, 1.5, 1.5]
    )
    with business_column:
        business_name = st.text_input(
            "Business name *", placeholder="Your business", key="business_name"
        )
    with customer_column:
        customer_name = st.text_input(
            "Customer name *", placeholder="Your customer", key="customer_name"
        )
    with number_column:
        invoice_number = st.text_input("Invoice number", key="invoice_number", disabled=True)
    with currency_column:
        currency = st.selectbox(
            "Invoice currency",
            options=list(SUPPORTED_CURRENCIES),
            format_func=lambda code: f"{code} - {SUPPORTED_CURRENCIES[code]}",
            key="invoice_currency",
        )
    terms_column, due_date_column = st.columns([1, 1], vertical_alignment="center")
    with terms_column:
        payment_terms = st.selectbox(
            "Payment terms",
            options=list(PAYMENT_TERMS_DAYS),
            key="payment_terms",
        )
    issue_date = date.today()
    due_date = issue_date + timedelta(days=PAYMENT_TERMS_DAYS[payment_terms])
    with due_date_column:
        st.caption("Due date")
        st.markdown(f"**{due_date.strftime('%B %d, %Y')}**")
    discount_column, tax_column = st.columns(2)
    with discount_column:
        discount_percent = st.number_input(
            "Discount (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.2f",
            key="discount_percent",
        )
    with tax_column:
        tax_percent = st.number_input(
            "Tax/VAT (%)",
            min_value=0.0,
            max_value=100.0,
            step=1.0,
            format="%.2f",
            help="Use the tax rate applicable to your invoice.",
            key="tax_percent",
        )

with st.expander("Business details", expanded=False, icon=":material/storefront:"):
    address = st.text_area(
        "Business address", placeholder="Street, city, postal code", key="business_address"
    )
    phone_column, email_column, tax_column = st.columns(3)
    with phone_column:
        phone = st.text_input("Phone", placeholder="+254 700 000 000", key="business_phone")
    with email_column:
        email = st.text_input("Email", placeholder="billing@example.com", key="business_email")
    with tax_column:
        tax_number = st.text_input("Tax/VAT number", placeholder="Optional", key="business_tax_number")
    mpesa_number = st.text_input(
        "M-Pesa Paybill/Till number", placeholder="Optional", key="business_mpesa_number"
    )
    logo = st.file_uploader(
        "Business logo", type=["png", "jpg", "jpeg"], key="business_logo"
    )
    if logo:
        st.session_state.invoice_draft_logo_bytes = logo.getvalue()
        st.session_state.invoice_draft_logo_name = logo.name
    elif st.session_state.get("invoice_draft_logo_bytes"):
        st.caption(f"Retained logo: {st.session_state.invoice_draft_logo_name}")
        if st.button("Remove saved logo", key="remove_saved_logo"):
            st.session_state.pop("invoice_draft_logo_bytes", None)
            st.session_state.pop("invoice_draft_logo_name", None)
            st.rerun()
    logo_bytes = logo.getvalue() if logo else st.session_state.get("invoice_draft_logo_bytes")
    logo_name = logo.name if logo else st.session_state.get("invoice_draft_logo_name", "")
    payment_instructions = st.text_area(
        "Payment instructions",
        placeholder="Bank transfer, mobile payment, or other payment details",
        key="payment_instructions",
    )

business_details = {
    "address": address,
    "phone": phone,
    "email": email,
    "tax_number": tax_number,
    "mpesa_number": mpesa_number,
}

with st.expander("Customer details", expanded=False, icon=":material/person:"):
    customer_address = st.text_area(
        "Customer address",
        placeholder="Street, city, postal code",
        key="customer_address",
    )
    customer_phone_column, customer_email_column, reference_column = st.columns(3)
    with customer_phone_column:
        customer_phone = st.text_input("Customer phone", placeholder="Optional", key="customer_phone")
    with customer_email_column:
        customer_email = st.text_input("Customer email", placeholder="Optional", key="customer_email")
    with reference_column:
        purchase_order = st.text_input(
            "Purchase order / reference", placeholder="Optional", key="purchase_order"
        )

customer_details = {
    "address": customer_address,
    "phone": customer_phone,
    "email": customer_email,
}

st.subheader("Line items", icon=":material/list_alt:")
st.caption("Fields marked * are required.")
with st.form("add_product_form", clear_on_submit=True, border=False):
    name_column, quantity_column, price_column, currency_column = st.columns(
        [3, 1, 1.3, 1.7], vertical_alignment="bottom"
    )
    with name_column:
        product_name = st.text_input(
            "Product name *", placeholder="e.g. Design service", key="product_name"
        )
    with quantity_column:
        quantity = st.number_input("Quantity *", min_value=1, step=1, key="product_quantity")
    with price_column:
        price = st.number_input(
            "Unit price *",
            min_value=1,
            step=1,
            format="%.2f",
            key="product_price",
        )
    with currency_column:
        price_currency = st.selectbox(
            "Price currency",
            options=list(SUPPORTED_CURRENCIES),
            format_func=lambda code: f"{code} - {SUPPORTED_CURRENCIES[code]}",
            key="price_currency",
        )
    add_product = st.form_submit_button(
        "Add product",
        type="primary",
        icon=":material/add:",
        width="stretch",
    )

if add_product:
    if not product_name.strip():
        st.error("Enter a product name before adding it.")
    else:
        st.session_state.products.append(
            {
                "name": product_name.strip(),
                "quantity": quantity,
                "price": price,
                "currency": price_currency,
            }
        )
        st.rerun()

products = st.session_state.products
invoice_products = []
conversion_error = None
invoice_amounts = None

for product in products:
    source_currency = product.get("currency", "KES")
    try:
        if source_currency == currency:
            converted_price = product["price"]
        else:
            exchange_data = cached_exchange_rates(source_currency)
            rate = exchange_data["rates"][currency]
            converted_price = convert_amount(product["price"], rate)
        invoice_products.append(
            {**product, "price": converted_price, "currency": currency}
        )
    except (ExchangeRateError, KeyError, ValueError) as error:
        conversion_error = error
        break

if conversion_error:
    st.warning(
        f"Could not load the {currency} exchange rate ({conversion_error}). "
        "Showing saved prices in their entry currencies; downloads are unavailable until "
        "conversion succeeds."
    )
elif products:
    invoice_amounts = calculate_invoice_amounts(
        invoice_products,
        discount_percent=discount_percent,
        tax_percent=tax_percent,
    )

st.subheader("Invoice preview", icon=":material/description:")
if products:
    preview_products = products if conversion_error else invoice_products
    with st.container(border=True):
        document_header, document_meta = st.columns([3, 1.5], vertical_alignment="top")
        with document_header:
            if logo:
                logo_column, business_column = st.columns([1, 4], vertical_alignment="center")
                with logo_column:
                    st.image(
                        logo.getvalue(),
                        width=88,
                        alt=f"{business_name or 'Business'} logo",
                    )
                with business_column:
                    st.markdown(f"### {business_name.strip() or 'Your business'}")
            else:
                st.markdown(f"### {business_name.strip() or 'Your business'}")
            contact_details = [value.strip() for value in (address, phone, email) if value.strip()]
            if tax_number.strip():
                contact_details.append(f"Tax/VAT: {tax_number.strip()}")
            if contact_details:
                st.caption(" · ".join(contact_details))
        with document_meta:
            st.markdown("**INVOICE**")
            st.markdown(f"**{invoice_number.strip()}**")
            st.caption(f"Issued {issue_date.strftime('%B %d, %Y')}")
            st.caption(f"Due {due_date.strftime('%B %d, %Y')}")

        recipient_column, payment_column = st.columns([1.5, 1], vertical_alignment="top")
        with recipient_column:
            st.markdown("**BILL TO**")
            recipient_lines = [customer_name.strip() or "Customer name"]
            recipient_lines.extend(
                value.strip()
                for value in (customer_address, customer_phone, customer_email)
                if value.strip()
            )
            st.markdown("  \n".join(recipient_lines))
        with payment_column:
            st.markdown("**PAYMENT TERMS**")
            st.write(payment_terms)
            st.caption(f"Payment reference: {invoice_number.strip()}")
            if purchase_order.strip():
                st.caption(f"Reference: {purchase_order.strip()}")
        st.space("small")

        header_columns = st.columns([3.2, 0.7, 1.35, 1.4, 0.8], vertical_alignment="center")
        for column, label in zip(
            header_columns,
            ("Product", "Qty", "Unit price", "Amount", ""),
        ):
            if label:
                column.markdown(f"**{label}**")
        for index, product in enumerate(preview_products):
            item_column, quantity_column, price_column, total_column, remove_column = st.columns(
                [3.2, 0.7, 1.35, 1.4, 0.8], vertical_alignment="center"
            )
            product_currency = product.get("currency", "KES") if conversion_error else currency
            item_column.write(product["name"])
            quantity_column.write(str(product["quantity"]))
            price_column.write(format_currency(product["price"], product_currency))
            line_total = product["price"] * product["quantity"]
            total_column.write(format_currency(line_total, product_currency))
            remove_column.button(
                "Remove",
                key=f"remove_product_{index}",
                on_click=remove_product,
                args=(index,),
                type="tertiary",
            )

        if not conversion_error:
            st.space("small")
            for label, amount in invoice_total_rows(invoice_amounts):
                label_column, amount_column = st.columns([1.2, 1], vertical_alignment="center")
                if label == "Amount due":
                    label_column.markdown("### Amount due")
                    amount_column.markdown(
                        f"### {format_currency(amount, currency)}",
                        text_alignment="right",
                    )
                else:
                    label_column.write(label)
                    amount_column.markdown(
                        format_currency(amount, currency),
                        text_alignment="right",
                    )
        invoice_payment_instructions = []
        if mpesa_number.strip():
            invoice_payment_instructions.append(
                f"M-Pesa Paybill/Till: {mpesa_number.strip()}. "
                f"Use invoice {invoice_number.strip()} as the account/reference."
            )
        if payment_instructions.strip():
            invoice_payment_instructions.append(payment_instructions.strip())
        if invoice_payment_instructions:
            st.markdown("**Payment instructions**")
            st.write("\n\n".join(invoice_payment_instructions))

    invoice_errors = validate_invoice_required_fields(
        business_name,
        customer_name,
        invoice_number,
        products,
        business_details,
    )
    for error in invoice_errors.values():
        st.error(error)

    if conversion_error:
        st.info("Complete invoice downloads will be available when exchange rates can be loaded.")
    elif not invoice_errors:
        st.badge(
            f"Invoice {invoice_number.strip()} is ready",
            icon=":material/check_circle:",
            color="green",
        )
        invoice_filename = f"invoice-{invoice_number.strip()}"
        logo_bytes = logo.getvalue() if logo else None
        csv_content = generate_invoice_csv(
            business_name.strip(),
            customer_name.strip(),
            invoice_products,
            invoice_number=invoice_number.strip(),
            currency=currency,
            business_details=business_details,
            logo_name=logo.name if logo else "",
            invoice_date=issue_date.isoformat(),
            due_date=due_date.isoformat(),
            payment_terms=payment_terms,
            customer_details=customer_details,
            purchase_order=purchase_order,
            payment_instructions=payment_instructions,
            discount_percent=discount_percent,
            tax_percent=tax_percent,
        )
        pdf_content = generate_invoice_pdf(
            business_name.strip(),
            customer_name.strip(),
            invoice_products,
            invoice_number=invoice_number.strip(),
            currency=currency,
            business_details=business_details,
            logo_bytes=logo_bytes,
            invoice_date=issue_date.strftime("%B %d, %Y"),
            due_date=due_date.strftime("%B %d, %Y"),
            payment_terms=payment_terms,
            customer_details=customer_details,
            purchase_order=purchase_order,
            payment_instructions=payment_instructions,
            discount_percent=discount_percent,
            tax_percent=tax_percent,
        )
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                "Save to history",
                icon=":material/save:",
                key=f"save_invoice_{invoice_number.strip()}",
            ):
                save_invoice_record(
                    invoice_number=invoice_number.strip(),
                    invoice_date=issue_date.isoformat(),
                    business_name=business_name.strip(),
                    customer_name=customer_name.strip(),
                    currency=currency,
                    total=format_currency(invoice_amounts["amount_due"], currency),
                    csv_content=csv_content,
                    pdf_content=pdf_content,
                )
                st.success("Invoice saved to history.")
            st.download_button(
                "CSV",
                data=csv_content,
                file_name=f"{invoice_filename}.csv",
                mime="text/csv",
                icon=":material/table_view:",
                help="Download invoice as CSV",
            )
            st.download_button(
                "PDF",
                data=pdf_content,
                file_name=f"{invoice_filename}.pdf",
                mime="application/pdf",
                type="primary",
                icon=":material/picture_as_pdf:",
                help="Download invoice as PDF",
            )
    else:
        st.info("Correct the business information and enter the customer name to complete the invoice.")
else:
    st.info("Add a product above to see the invoice preview.")
