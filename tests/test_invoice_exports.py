import csv
import io
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from invoice_generator import (
    calculate_invoice_amounts,
    generate_invoice_csv,
    generate_invoice_pdf,
    validate_invoice_required_fields,
)
from invoice_history import get_invoice_record, list_invoice_history, save_invoice_record


class InvoiceExportTests(unittest.TestCase):
    def setUp(self):
        self.products = [{"name": "Brand design", "quantity": 2, "price": 125.5}]
        self.details = {
            "address": "12 Market Street, Nairobi",
            "phone": "+254 700 123 456",
            "email": "billing@example.com",
            "tax_number": "VAT-KE-123",
            "mpesa_number": "123456",
        }
        self.customer_details = {
            "address": "24 Client Road, Nairobi",
            "phone": "+254 711 222 333",
            "email": "avery@example.com",
        }
        logo = Image.new("RGB", (48, 24), color="#176B57")
        self.logo_buffer = io.BytesIO()
        logo.save(self.logo_buffer, format="PNG")
        self.logo_bytes = self.logo_buffer.getvalue()

    def test_csv_contains_business_details_currency_logo_and_totals(self):
        csv_content = generate_invoice_csv(
            "Northstar Studio",
            "Avery Chen",
            self.products,
            invoice_number="INV-20261013-100",
            currency="USD",
            business_details=self.details,
            logo_name="northstar-logo.png",
            invoice_date="2026-10-13",
            due_date="2026-11-12",
            payment_terms="Net 30 days",
            customer_details=self.customer_details,
            purchase_order="PO-456",
            payment_instructions="Pay by bank transfer to account 123456.",
            discount_percent=10,
            tax_percent=16,
        )
        rows = list(csv.reader(io.StringIO(csv_content)))
        values = {row[0]: row[1] for row in rows if len(row) == 2 and row[0]}

        self.assertEqual(values["Invoice number"], "INV-20261013-100")
        self.assertEqual(values["Invoice date"], "2026-10-13")
        self.assertEqual(values["Due date"], "2026-11-12")
        self.assertEqual(values["Payment terms"], "Net 30 days")
        self.assertEqual(values["Purchase order / reference"], "PO-456")
        self.assertEqual(values["Currency"], "USD")
        self.assertEqual(values["Business"], "Northstar Studio")
        self.assertEqual(values["Business address"], self.details["address"])
        self.assertEqual(values["Phone"], self.details["phone"])
        self.assertEqual(values["Email"], self.details["email"])
        self.assertEqual(values["Tax/VAT number"], self.details["tax_number"])
        self.assertEqual(values["M-Pesa Paybill/Till"], self.details["mpesa_number"])
        self.assertEqual(values["Business logo"], "northstar-logo.png")
        self.assertEqual(values["Customer address"], self.customer_details["address"])
        self.assertEqual(values["Customer phone"], self.customer_details["phone"])
        self.assertEqual(values["Customer email"], self.customer_details["email"])
        self.assertEqual(values["Payment instructions"], "Pay by bank transfer to account 123456.")
        self.assertIn(["Brand design", "2", "125.50", "251.00"], rows)
        self.assertIn(["", "", "Subtotal", "251.00"], rows)
        self.assertIn(["", "", "Discount (10%)", "-25.10"], rows)
        self.assertIn(["", "", "Tax/VAT (16%)", "36.14"], rows)
        self.assertIn(["", "", "Amount due", "262.04"], rows)
        self.assertTrue(any("Unit price (USD)" in cell for row in rows for cell in row))

    def test_pdf_contains_logo_business_details_currency_and_total(self):
        pdf_content = generate_invoice_pdf(
            "Northstar Studio",
            "Avery Chen",
            self.products,
            invoice_number="INV-20261013-100",
            currency="USD",
            business_details=self.details,
            logo_bytes=self.logo_bytes,
            invoice_date="October 13, 2026",
            due_date="November 12, 2026",
            payment_terms="Net 30 days",
            customer_details=self.customer_details,
            purchase_order="PO-456",
            payment_instructions="Pay by bank transfer to account 123456.",
            discount_percent=10,
            tax_percent=16,
        )
        reader = PdfReader(io.BytesIO(pdf_content))
        page = reader.pages[0]
        text = page.extract_text()

        for expected in (
            "Northstar Studio",
            "BILL TO",
            "12 Market Street, Nairobi",
            "+254 700 123 456",
            "billing@example.com",
            "VAT-KE-123",
            "Avery Chen",
            "INV-20261013-100",
            "Invoice date",
            "October 13, 2026",
            "Due date",
            "November 12, 2026",
            "Net 30 days",
            "PAYMENT TERMS",
            "PO-456",
            "24 Client Road, Nairobi",
            "+254 711 222 333",
            "avery@example.com",
            "Unit price (USD)",
            "USD 251.00",
            "Discount (10%)",
            "USD -25.10",
            "Tax/VAT (16%)",
            "USD 36.14",
            "USD 262.04",
            "Pay by bank transfer to account 123456.",
            "M-Pesa Paybill/Till: 123456.",
            "Use invoice INV-20261013-100 as the account/reference.",
            "Payment reference: INV-20261013-100",
            "Terms: Net 30 days",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("<b>", text)
        self.assertLess(text.index("INV-20261013-100"), text.index("Invoice date"))
        self.assertLess(text.index("Invoice date"), text.index("Due date"))
        self.assertEqual(len(page.images), 1)

    def test_long_pdf_repeats_table_heading_and_numbers_pages(self):
        products = [
            {"name": f"Service item {index}", "quantity": 1, "price": 25.0}
            for index in range(1, 45)
        ]
        pdf_content = generate_invoice_pdf(
            "Northstar Studio",
            "Avery Chen",
            products,
            invoice_number="INV-20261013-101",
            currency="USD",
            invoice_date="October 13, 2026",
            due_date="November 12, 2026",
            payment_terms="Net 30 days",
        )
        pages = PdfReader(io.BytesIO(pdf_content)).pages

        self.assertGreater(len(pages), 1)
        self.assertIn("Description", pages[1].extract_text())
        self.assertIn(f"Page {len(pages)}", pages[-1].extract_text())

    def test_invoice_amount_calculation_applies_discount_before_tax(self):
        totals = calculate_invoice_amounts(self.products, discount_percent=10, tax_percent=16)
        self.assertEqual(totals["subtotal"], Decimal("251.00"))
        self.assertEqual(totals["discount"], Decimal("25.10"))
        self.assertEqual(totals["tax"], Decimal("36.14"))
        self.assertEqual(totals["amount_due"], Decimal("262.04"))

    def test_zero_adjustments_produce_no_discount_or_tax(self):
        totals = calculate_invoice_amounts(self.products)
        self.assertEqual(totals["discount"], Decimal("0.00"))
        self.assertEqual(totals["tax"], Decimal("0.00"))
        self.assertEqual(totals["amount_due"], Decimal("251.00"))

    def test_required_invoice_fields_and_saved_product_lines_are_validated(self):
        valid_errors = validate_invoice_required_fields(
            "Northstar Studio",
            "Avery Chen",
            "INV-20261013-100",
            self.products,
        )
        invalid_errors = validate_invoice_required_fields(
            "",
            "x" * 121,
            "",
            [
                {"name": "", "quantity": 0, "price": -1, "currency": "XXX"},
                {"name": "Bad quantity", "quantity": 1.5, "price": "bad"},
            ],
        )

        self.assertEqual(valid_errors, {})
        self.assertIn("business_name", invalid_errors)
        self.assertIn("customer_name", invalid_errors)
        self.assertIn("invoice_number", invalid_errors)
        self.assertIn("product_1_name", invalid_errors)
        self.assertIn("product_1_quantity", invalid_errors)
        self.assertIn("product_1_price", invalid_errors)
        self.assertIn("product_1_currency", invalid_errors)
        self.assertIn("product_2_quantity", invalid_errors)
        self.assertIn("product_2_price", invalid_errors)

    def test_saved_invoice_survives_database_reopen_with_both_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "history.sqlite3"
            pdf_content = generate_invoice_pdf(
                "Northstar Studio",
                "Avery Chen",
                self.products,
                invoice_number="INV-20261013-100",
                currency="USD",
                business_details=self.details,
                logo_bytes=self.logo_bytes,
                invoice_date="October 13, 2026",
                due_date="November 12, 2026",
                payment_terms="Net 30 days",
                customer_details=self.customer_details,
                purchase_order="PO-456",
                payment_instructions="Pay by bank transfer to account 123456.",
            )
            csv_content = generate_invoice_csv(
                "Northstar Studio",
                "Avery Chen",
                self.products,
                invoice_number="INV-20261013-100",
                currency="USD",
                business_details=self.details,
                logo_name="northstar-logo.png",
                invoice_date="2026-10-13",
                due_date="2026-11-12",
                payment_terms="Net 30 days",
                customer_details=self.customer_details,
                purchase_order="PO-456",
                payment_instructions="Pay by bank transfer to account 123456.",
            )
            save_invoice_record(
                invoice_number="INV-20261013-100",
                invoice_date="2026-10-13",
                business_name="Northstar Studio",
                customer_name="Avery Chen",
                currency="USD",
                total="USD 251.00",
                csv_content=csv_content,
                pdf_content=pdf_content,
                database_path=database_path,
            )

            history = list_invoice_history(database_path)
            saved = get_invoice_record("INV-20261013-100", database_path)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["total"], "USD 251.00")
        self.assertEqual(saved["csv_content"], csv_content)
        self.assertEqual(saved["pdf_content"], pdf_content)


if __name__ == "__main__":
    unittest.main()