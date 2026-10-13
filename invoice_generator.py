import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
import sqlite3

def validate_required_name(value: str, field_name: str) -> str | None:
    """Return an error message when a required name contains no text."""
    if not value.strip():
        return f"{field_name} cannot be empty."
    return None


def allocate_invoice_number(existing_number: str | None = None, database_path=None) -> str:
    """Register an existing invoice number or atomically allocate the next one."""
    database_path = Path(database_path) if database_path else Path(__file__).with_name(
        "invoice_numbers.sqlite3"
    )
    connection = sqlite3.connect(database_path, timeout=30)
    try:
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS invoice_number_counters (
                invoice_date TEXT PRIMARY KEY,
                last_sequence INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS issued_invoice_numbers (
                invoice_number TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("BEGIN IMMEDIATE")

        if existing_number:
            match = re.fullmatch(r"INV-(\d{8})-(\d+)", existing_number)
            if not match:
                raise ValueError("Existing invoice number has an invalid format.")
            invoice_date, sequence = match.group(1), int(match.group(2))
            connection.execute(
                "INSERT OR IGNORE INTO issued_invoice_numbers (invoice_number) VALUES (?)",
                (existing_number,),
            )
            connection.execute(
                """
                INSERT INTO invoice_number_counters (invoice_date, last_sequence)
                VALUES (?, ?)
                ON CONFLICT(invoice_date) DO UPDATE SET
                    last_sequence = MAX(last_sequence, excluded.last_sequence)
                """,
                (invoice_date, sequence),
            )
            invoice_number = existing_number
        else:
            invoice_date = date.today().strftime("%Y%m%d")
            row = connection.execute(
                "SELECT last_sequence FROM invoice_number_counters WHERE invoice_date = ?",
                (invoice_date,),
            ).fetchone()
            sequence = row[0] + 1 if row else 1

            while True:
                invoice_number = f"INV-{invoice_date}-{sequence:03d}"
                try:
                    connection.execute(
                        "INSERT INTO issued_invoice_numbers (invoice_number) VALUES (?)",
                        (invoice_number,),
                    )
                    break
                except sqlite3.IntegrityError:
                    sequence += 1

            connection.execute(
                """
                INSERT INTO invoice_number_counters (invoice_date, last_sequence)
                VALUES (?, ?)
                ON CONFLICT(invoice_date) DO UPDATE SET last_sequence = excluded.last_sequence
                """,
                (invoice_date, sequence),
            )

        connection.commit()
        return invoice_number
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def validate_business_information(
    business_name: str,
    address: str = "",
    phone: str = "",
    email: str = "",
    tax_number: str = "",
) -> dict[str, str]:
    """Return validation errors for business details used on an invoice."""
    errors = {}
    name_error = validate_required_name(business_name, "Business name")
    if name_error:
        errors["business_name"] = name_error
    elif len(business_name.strip()) > 120:
        errors["business_name"] = "Business name must be 120 characters or fewer."

    if len(address.strip()) > 250:
        errors["address"] = "Business address must be 250 characters or fewer."

    normalized_phone = phone.strip()
    if normalized_phone:
        phone_digits = re.sub(r"\D", "", normalized_phone)
        if (
            not re.fullmatch(r"\+?[0-9().\-\s]+", normalized_phone)
            or not 7 <= len(phone_digits) <= 15
        ):
            errors["phone"] = (
            "Enter a phone number with 7 to 15 digits."
        )

    normalized_email = email.strip()
    if normalized_email and (
        len(normalized_email) > 254
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email)
    ):
        errors["email"] = "Enter a valid email address."

    normalized_tax_number = tax_number.strip()
    if normalized_tax_number and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9 ./-]{0,49}", normalized_tax_number
    ):
        errors["tax_number"] = "Tax/VAT number must be at most 50 characters using letters, numbers, spaces, ., /, or -."

    return errors


def validate_invoice_required_fields(
    business_name,
    customer_name,
    invoice_number,
    products,
    business_details=None,
):
    """Validate required invoice identity and every saved product line."""
    details = business_details or {}
    errors = validate_business_information(
        business_name,
        details.get("address", ""),
        details.get("phone", ""),
        details.get("email", ""),
        details.get("tax_number", ""),
    )

    customer_error = validate_required_name(customer_name, "Customer name")
    if customer_error:
        errors["customer_name"] = customer_error
    elif len(customer_name.strip()) > 120:
        errors["customer_name"] = "Customer name must be 120 characters or fewer."

    invoice_number_error = validate_required_name(invoice_number, "Invoice number")
    if invoice_number_error:
        errors["invoice_number"] = invoice_number_error

    if not products:
        errors["products"] = "Add at least one product to the invoice."
        return errors

    for index, product in enumerate(products, start=1):
        if not isinstance(product, dict):
            errors[f"product_{index}"] = f"Product {index} is invalid. Remove it and add it again."
            continue

        name = product.get("name")
        if not isinstance(name, str) or not name.strip():
            errors[f"product_{index}_name"] = f"Product {index} name cannot be empty."

        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, ValueError):
            price = Decimal("NaN")
        if not price.is_finite() or price <= 0:
            errors[f"product_{index}_price"] = f"Product {index} price must be a positive number."

        try:
            quantity = Decimal(str(product.get("quantity")))
        except (InvalidOperation, ValueError):
            quantity = Decimal("NaN")
        if not quantity.is_finite() or quantity <= 0 or quantity != quantity.to_integral_value():
            errors[f"product_{index}_quantity"] = (
                f"Product {index} quantity must be a positive whole number."
            )

        if product.get("currency", "KES") not in SUPPORTED_CURRENCIES:
            errors[f"product_{index}_currency"] = f"Product {index} has an unsupported currency."

    return errors


def get_product():
    """Prompt the user for a product and return a product dictionary."""
    while True:
        try:
            product = {
                "name": input("Please enter the product name: ").strip(),
                "price": float(input("Please enter the product price: ")),
                "quantity": int(input("Please enter the product quantity: "))
            }

            if not product["name"]:
                print("Product name cannot be empty. Please enter a valid name.")
                continue
            if product["price"] <= 0:
                print("Product price cannot be zero or negative. Please enter a valid price.")
                continue
            if product["quantity"] <= 0:
                print("Product quantity cannot be zero or negative. Please enter a valid quantity.")
                continue

            return product
        except ValueError:
            print("Invalid input. Please enter valid numbers for price and quantity.")


def calculate_invoice_total(products):
    """Return the total value of all products in the invoice."""
    return sum(product["price"] * product["quantity"] for product in products)


def calculate_invoice_amounts(products, discount_percent=0, tax_percent=0):
    """Calculate subtotal, optional discount and tax, and final amount due."""
    discount_rate = Decimal(str(discount_percent))
    tax_rate = Decimal(str(tax_percent))
    if not discount_rate.is_finite() or not Decimal("0") <= discount_rate <= Decimal("100"):
        raise ValueError("Discount percent must be between 0 and 100.")
    if not tax_rate.is_finite() or not Decimal("0") <= tax_rate <= Decimal("100"):
        raise ValueError("Tax percent must be between 0 and 100.")

    cent = Decimal("0.01")
    subtotal = sum(
        (
            Decimal(str(product["price"])) * Decimal(str(product["quantity"]))
        ).quantize(cent, rounding=ROUND_HALF_UP)
        for product in products
    )
    discount = (subtotal * discount_rate / Decimal("100")).quantize(
        cent, rounding=ROUND_HALF_UP
    )
    taxable_amount = subtotal - discount
    tax = (taxable_amount * tax_rate / Decimal("100")).quantize(
        cent, rounding=ROUND_HALF_UP
    )
    return {
        "subtotal": subtotal,
        "discount": discount,
        "discount_percent": discount_rate,
        "tax": tax,
        "tax_percent": tax_rate,
        "amount_due": taxable_amount + tax,
    }


def invoice_total_rows(amounts):
    """Return labeled subtotal, applicable adjustments, and amount-due rows."""
    rows = [("Subtotal", amounts["subtotal"])]
    if amounts["discount_percent"] > 0:
        rows.append(
            (
                f"Discount ({amounts['discount_percent']:g}%)",
                -amounts["discount"],
            )
        )
    if amounts["tax_percent"] > 0:
        rows.append(
            (
                f"Tax/VAT ({amounts['tax_percent']:g}%)",
                amounts["tax"],
            )
        )
    rows.append(("Amount due", amounts["amount_due"]))
    return rows


def generate_invoice_csv(
    business_name,
    customer_name,
    products,
    invoice_number="",
    currency="KES",
    business_details=None,
    logo_name="",
    invoice_date="",
    due_date="",
    payment_terms="",
    customer_details=None,
    purchase_order="",
    payment_instructions="",
    discount_percent=0,
    tax_percent=0,
):
    """Create CSV invoice contents from the same data used by the PDF export."""
    details = business_details or {}
    recipient = customer_details or {}
    currency_label = "Kshs." if currency == "KES" else currency
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Invoice number", invoice_number])
    writer.writerow(["Invoice date", invoice_date])
    writer.writerow(["Due date", due_date])
    writer.writerow(["Payment terms", payment_terms])
    writer.writerow(["Purchase order / reference", purchase_order])
    writer.writerow(["Currency", currency])
    writer.writerow(["Business", business_name])
    writer.writerow(["Business address", details.get("address", "")])
    writer.writerow(["Phone", details.get("phone", "")])
    writer.writerow(["Email", details.get("email", "")])
    writer.writerow(["Tax/VAT number", details.get("tax_number", "")])
    if details.get("mpesa_number", "").strip():
        writer.writerow(["M-Pesa Paybill/Till", details["mpesa_number"].strip()])
    if logo_name:
        writer.writerow(["Business logo", logo_name])
    writer.writerow(["Customer", customer_name])
    writer.writerow(["Customer address", recipient.get("address", "")])
    writer.writerow(["Customer phone", recipient.get("phone", "")])
    writer.writerow(["Customer email", recipient.get("email", "")])
    writer.writerow(["Payment instructions", payment_instructions])
    writer.writerow([])
    writer.writerow(
        ["Product", "Quantity", f"Unit price ({currency_label})", f"Amount ({currency_label})"]
    )
    for product in products:
        writer.writerow(
            [
                product["name"],
                product["quantity"],
                f'{product["price"]:,.2f}',
                f'{product["price"] * product["quantity"]:,.2f}',
            ]
        )
    totals = calculate_invoice_amounts(products, discount_percent, tax_percent)
    for label, amount in invoice_total_rows(totals):
        writer.writerow(["", "", label, f"{amount:,.2f}"])
    return buffer.getvalue()


SUPPORTED_CURRENCIES = {
    "KES": "Kenyan Shilling",
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "UGX": "Ugandan Shilling",
    "TZS": "Tanzanian Shilling",
}


def format_currency(amount, currency="KES"):
    """Format an amount using the selected currency code."""
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {currency}")
    prefix = "Kshs." if currency == "KES" else currency
    return f"{prefix} {amount:,.2f}"


def generate_invoice_pdf(
    business_name,
    customer_name,
    products,
    invoice_number="",
    currency="KES",
    business_details=None,
    logo_bytes=None,
    invoice_date="",
    due_date="",
    payment_terms="",
    customer_details=None,
    purchase_order="",
    payment_instructions="",
    discount_percent=0,
    tax_percent=0,
):
    """Build a polished, paginated PDF invoice and return its contents as bytes."""
    import io
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    page_width, _ = letter
    left_margin = 0.58 * inch
    right_margin = 0.58 * inch
    bottom_margin = 0.72 * inch
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=0.55 * inch,
        bottomMargin=bottom_margin,
        title=f"Invoice {invoice_number}",
        author=business_name,
    )
    ink = colors.HexColor("#172B4D")
    green = colors.HexColor("#16806A")
    muted = colors.HexColor("#617286")
    border = colors.HexColor("#D9E2E8")
    pale = colors.HexColor("#F1F7F5")
    white = colors.white
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "InvoiceBusiness",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            textColor=ink,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceContact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=muted,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=ink,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=ink,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceNumber",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=ink,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=green,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceTableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=white,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceTotalLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=ink,
        )
    )
    styles.add(
        ParagraphStyle(
            "InvoiceTotalValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=green,
            alignment=TA_RIGHT,
        )
    )
    details = business_details or {}
    recipient = customer_details or {}

    def paragraph(value, style="InvoiceBody"):
        safe_value = escape(str(value)).replace("\n", "<br/>")
        return Paragraph(safe_value, styles[style])

    story = []
    business_lines = []
    for label, key in (
        ("Address", "address"),
        ("Phone", "phone"),
        ("Email", "email"),
        ("Tax/VAT number", "tax_number"),
    ):
        value = details.get(key, "").strip()
        if value:
            business_lines.append(f"{label}: {value}")
    business_content = [paragraph(business_name, "InvoiceBusiness")]
    if business_lines:
        business_content.append(paragraph("\n".join(business_lines), "InvoiceContact"))

    if logo_bytes:
        brand_mark = Image(
            io.BytesIO(logo_bytes),
            width=1.05 * inch,
            height=0.78 * inch,
            kind="proportional",
        )
        brand_block = Table(
            [[brand_mark, business_content]],
            colWidths=[1.0 * inch, 3.35 * inch],
        )
    else:
        brand_block = Table(
            [[business_content]],
            colWidths=[4.35 * inch],
        )

    issue_value = invoice_date or date.today().strftime("%B %d, %Y")
    due_value = due_date or "Not specified"
    meta_rows = [
        [paragraph("INVOICE", "InvoiceTitle")],
        [paragraph(invoice_number, "InvoiceNumber")],
        [paragraph(f"Invoice date: {issue_value}", "InvoiceMeta")],
        [paragraph(f"Due date: {due_value}", "InvoiceMeta")],
    ]
    meta_block = Table(meta_rows, colWidths=[2.55 * inch], hAlign="RIGHT")
    meta_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    header = Table(
        [[brand_block, meta_block]],
        colWidths=[4.55 * inch, 2.55 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.extend([header, Spacer(1, 0.16 * inch), HRFlowable(width="100%", thickness=1.3, color=green)])
    story.append(Spacer(1, 0.23 * inch))

    customer_lines = [
        paragraph("BILL TO", "InvoiceLabel"),
        paragraph(customer_name, "InvoiceBusiness"),
    ]
    for label, key in (
        ("Customer address", "address"),
        ("Customer phone", "phone"),
        ("Customer email", "email"),
    ):
        value = recipient.get(key, "").strip()
        if value:
            customer_lines.append(paragraph(value, "InvoiceContact"))
    terms_lines = [
        paragraph("PAYMENT TERMS", "InvoiceLabel"),
        paragraph(payment_terms or "Terms not specified", "InvoiceBody"),
    ]
    if purchase_order.strip():
        terms_lines.append(paragraph(f"Reference: {purchase_order.strip()}", "InvoiceContact"))
    parties = Table(
        [[customer_lines, terms_lines]],
        colWidths=[4.35 * inch, 2.75 * inch],
    )
    parties.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (1, 0), (1, 0), pale),
                ("BOX", (1, 0), (1, 0), 0.6, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 12),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("RIGHTPADDING", (1, 0), (1, 0), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([parties, Spacer(1, 0.3 * inch)])

    currency_label = "Kshs." if currency == "KES" else currency
    table_data = [[
        paragraph("Description", "InvoiceTableHeader"),
        paragraph("Qty", "InvoiceTableHeader"),
        paragraph(f"Unit price ({currency_label})", "InvoiceTableHeader"),
        paragraph(f"Line total ({currency_label})", "InvoiceTableHeader"),
    ]]
    table_data.extend(
        [
            paragraph(product["name"]),
            paragraph(product["quantity"]),
            paragraph(format_currency(product["price"], currency)),
            paragraph(format_currency(product["price"] * product["quantity"], currency)),
        ]
        for product in products
    )
    invoice_table = Table(
        table_data,
        colWidths=[3.3 * inch, 0.55 * inch, 1.55 * inch, 1.7 * inch],
        repeatRows=1,
        hAlign="LEFT",
    )
    invoice_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ink),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (1, 0), (-1, 0), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, pale]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, green),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([invoice_table, Spacer(1, 0.18 * inch)])

    totals = calculate_invoice_amounts(products, discount_percent, tax_percent)
    total_rows = []
    for label, amount in invoice_total_rows(totals):
        is_amount_due = label == "Amount due"
        label_style = "InvoiceTotalLabel" if is_amount_due else "InvoiceContact"
        value_style = "InvoiceTotalValue" if is_amount_due else "InvoiceMeta"
        total_rows.append(
            [
                paragraph(label, label_style),
                paragraph(format_currency(amount, currency), value_style),
            ]
        )
    total_block = Table(
        total_rows,
        colWidths=[1.35 * inch, 1.8 * inch],
        hAlign="RIGHT",
    )
    final_row = len(total_rows) - 1
    total_block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, final_row), (-1, final_row), pale),
                ("LINEABOVE", (0, final_row), (-1, final_row), 0.7, border),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(total_block)

    instructions_lines = []
    mpesa_number = details.get("mpesa_number", "").strip()
    if mpesa_number:
        instructions_lines.append(
            f"M-Pesa Paybill/Till: {mpesa_number}. "
            f"Use invoice {invoice_number} as the account/reference."
        )
    if payment_instructions.strip():
        instructions_lines.append(payment_instructions.strip())
    if instructions_lines:
        instructions = Table(
            [[
                paragraph("PAYMENT INSTRUCTIONS", "InvoiceLabel"),
                paragraph("\n".join(instructions_lines)),
            ]],
            colWidths=[1.55 * inch, 5.55 * inch],
        )
        instructions.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), pale),
                    ("BOX", (0, 0), (-1, -1), 0.6, border),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.extend([Spacer(1, 0.28 * inch), instructions])

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.setLineWidth(0.5)
        canvas.line(left_margin, 0.48 * inch, page_width - right_margin, 0.48 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(left_margin, 0.32 * inch, "Thank you for your business")
        canvas.drawRightString(page_width - right_margin, 0.32 * inch, f"Page {doc.page}")
        footer_note = f"Payment reference: {invoice_number}"
        if payment_terms:
            footer_note += f"  |  Terms: {payment_terms}"
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(left_margin, 0.16 * inch, footer_note)
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buffer.getvalue()


def print_invoice(business_name, customer_name, products):
    """Print a formatted invoice summary for the given products."""
    total_price = calculate_invoice_total(products)
    product_name_width = max(24, max((len(product["name"]) for product in products), default=0))
    table_width = product_name_width + 45

    print("\nInvoice Summary:")
    print("=" * table_width)
    print(f"Business Name:\t{business_name}")
    print(f"Customer Name:\t{customer_name}")

    print("\nProduct Details:")
    print("=" * table_width)
    print(
        f"{'Product':<{product_name_width}} "
        f"{'Qty':>6} "
        f"{'Unit Price':>18} "
        f"{'Amount':>18}"
    )
    print("=" * table_width)

    for product in products:
        unit_price = f"Kshs. {product['price']:,.2f}"
        line_total = f"Kshs. {product['price'] * product['quantity']:,.2f}"
        print(
            f"{product['name']:<{product_name_width}} "
            f"{product['quantity']:>6} "
            f"{unit_price:>18} "
            f"{line_total:>18}"
        )

    print("=" * table_width)
    print(f"{'Invoice Total':>{table_width - 18}} {'Kshs. ' + format(total_price, ',.2f'):>18}")
    print("=" * table_width)


def main():
    print("Welcome to the Invoice Generator!")

    while True:
        business_name = input("Please enter your business name: ").strip()
        error = validate_required_name(business_name, "Business name")
        if error:
            print(f"{error} Please enter a valid name.")
            continue
        break
    print(f"Hello, {business_name}! \nLet's generate an invoice for your customer.")

    while True:
        customer_name = input("Please enter the customer's name: ").strip()
        error = validate_required_name(customer_name, "Customer name")
        if error:
            print(f"{error} Please enter a valid name.")
            continue
        break

    print(f"Great! Let's proceed to add products for {customer_name}.")
    products = []

    while True:
        products.append(get_product())

        while True:
            continue_adding = input("Do you want to add another product? (yes/no): ").strip().lower()
            if continue_adding in ["yes", "no"]:
                break
            print("Invalid input. Please enter 'yes' or 'no'.")

        if continue_adding == "no":
            break

    print_invoice(business_name, customer_name, products)
    print("\nThank you for using the Invoice Generator!")


if __name__ == "__main__":
    main()
