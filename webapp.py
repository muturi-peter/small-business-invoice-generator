import csv
import io

import streamlit as st

from invoice_generator import calculate_invoice_total, validate_required_name


def remove_product(index):
    st.session_state.products.pop(index)


st.set_page_config(page_title="Invoice Generator", page_icon="🧾", layout="wide")

if "products" not in st.session_state:
    st.session_state.products = []

st.title("Invoice Generator")
st.caption("Create a clear, itemized invoice for your customer.")

st.subheader("Invoice details")
business_column, customer_column = st.columns(2)
with business_column:
    business_name = st.text_input("Business name", placeholder="Your business")
with customer_column:
    customer_name = st.text_input("Customer name", placeholder="Your customer")

st.subheader("Add products")
with st.form("add_product_form", clear_on_submit=True):
    name_column, quantity_column, price_column = st.columns([3, 1, 2])
    with name_column:
        product_name = st.text_input("Product name", placeholder="e.g. Design service")
    with quantity_column:
        quantity = st.number_input("Quantity", min_value=1, step=1)
    with price_column:
        price = st.number_input(
            "Unit price (Kshs.)",
            min_value=1,
            step=1,
            format="%.2f",
        )
    add_product = st.form_submit_button("Add product", type="primary")

if add_product:
    if not product_name.strip():
        st.error("Enter a product name before adding it.")
    else:
        st.session_state.products.append(
            {
                "name": product_name.strip(),
                "quantity": quantity,
                "price": price,
            }
        )
        st.rerun()

st.subheader("Invoice preview")
products = st.session_state.products

if products:
    for index, product in enumerate(products):
        item_column, quantity_column, price_column, total_column, remove_column = st.columns(
            [3, 1, 1.5, 1.5, 1]
        )
        item_column.write(product["name"])
        quantity_column.write(str(product["quantity"]))
        price_column.write(f"Kshs. {product['price']:,.2f}")
        line_total = product["price"] * product["quantity"]
        total_column.write(f"Kshs. {line_total:,.2f}")
        remove_column.button(
            "Remove",
            key=f"remove_product_{index}",
            on_click=remove_product,
            args=(index,),
        )

    total_price = calculate_invoice_total(products)
    st.divider()
    summary_column, _ = st.columns([1, 2])
    with summary_column:
        st.metric("Invoice total", f"Kshs. {total_price:,.2f}")

    business_error = validate_required_name(business_name, "Business name")
    customer_error = validate_required_name(customer_name, "Customer name")
    if business_error:
        st.error(business_error)
    if customer_error:
        st.error(customer_error)

    if not business_error and not customer_error:
        st.success(f"Invoice for **{customer_name.strip()}** from **{business_name.strip()}** is ready.")
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Business", business_name.strip()])
        writer.writerow(["Customer", customer_name.strip()])
        writer.writerow([])
        writer.writerow(["Product", "Quantity", "Unit price (Kshs.)", "Amount (Kshs.)"])
        for product in products:
            writer.writerow(
                [
                    product["name"],
                    product["quantity"],
                    f'{product["price"]:.2f}',
                    f'{product["price"] * product["quantity"]:.2f}',
                ]
            )
        writer.writerow(["", "", "Invoice total", f"{total_price:.2f}"])
        st.download_button(
            "Download invoice as CSV",
            data=csv_buffer.getvalue(),
            file_name="invoice.csv",
            mime="text/csv",
            type="primary",
        )
    else:
        st.info("Enter both business and customer names to complete the invoice.")
else:
    st.info("Add a product above to see the invoice preview.")
