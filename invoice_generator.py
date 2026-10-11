def validate_required_name(value: str, field_name: str) -> str | None:
    """Return an error message when a required name contains no text."""
    if not value.strip():
        return f"{field_name} cannot be empty."
    return None


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
