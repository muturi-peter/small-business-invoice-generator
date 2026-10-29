# Small Business Invoice Generator

A Python-based web application built with Streamlit to help small businesses and freelancers create clear, itemized invoices.

> **Project status:** In development. Features and setup instructions may change as the project evolves.

## Overview

The Small Business Invoice Generator aims to make invoice creation simpler by bringing business and customer details, product line items, invoice totals, and invoice export into one interface.

The project is also a practical learning exercise in Python application development, input validation, API integration, and version control.

## Features

The current application is being developed around the following features:

- Enter business and customer information.
- Add products or services with quantities and prices.
- Calculate invoice totals automatically.
- Generate invoice numbers.
- Support multiple currencies.
- Convert amounts using exchange-rate data.
- Generate downloadable PDF invoices.
- Validate required fields and user input.
- Provide a Streamlit-based web interface.

Some features may still be under development. Check the code and latest commits for the current implementation.

## Technology Stack

- **Python** — application logic and calculations
- **Streamlit** — web interface
- **Git and GitHub** — version control and project hosting
- **PDF generation library** — invoice document export
- **Exchange-rate API** — currency conversion data
- **CSV and Python I/O tools** — data handling and file output

## Project Structure

The project may use a structure similar to the following:

```text
small-business-invoice-generator/
├── webapp.py                 # Streamlit application and user interface
├── invoice_generator.py   # Invoice calculations, validation, and PDF generation
├── exchange_rates.py      # Exchange-rate retrieval and currency conversion
├── requirements.txt       # Python package dependencies
├── .gitignore             # Files Git should ignore
└── README.md              # Project documentation
```

Your local repository may differ. Update this section if your filenames or folder structure change.

## Getting Started

### Prerequisites

- Python 3.10 or a compatible version supported by your dependencies
- Git
- Internet access for installing dependencies and retrieving exchange-rate data

### 1. Clone the repository

```bash
git clone https://github.com/muturi-peter/small-business-invoice-generator.git
cd small-business-invoice-generator
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

If the repository contains a `requirements.txt` file:

```bash
python -m pip install -r requirements.txt
```

If it does not, install the packages used by your current application and create a dependency file:

```bash
python -m pip install streamlit
python -m pip freeze > requirements.txt
```

Install any additional packages required by `invoice_generator.py` and `exchange_rates.py` before running the app.

### 4. Run the application

```bash
streamlit run webapp.py
```

Streamlit will provide a local URL to open in your browser.

## How to Use

1. Start the Streamlit application.
2. Enter your business information.
3. Enter the customer's details.
4. Add products or services, including quantity and unit price.
5. Review the calculated invoice total.
6. Select the available currency options as needed.
7. Generate and download the invoice PDF if PDF export is enabled in your current version.

The exact workflow depends on the features currently implemented in the repository.

## Configuration and API Notes

The application may retrieve exchange rates from an external API. Exchange-rate availability depends on the selected provider and an active internet connection.

- Do not commit API keys, passwords, tokens, or other secrets to GitHub.
- Store secrets in environment variables or Streamlit's secrets configuration when required.
- Add local secret files to `.gitignore`.
- Handle network errors and unavailable exchange-rate data gracefully.

## Development Goals

Planned improvements may include:

- A more polished, responsive dashboard.
- Stronger automated tests for invoice calculations and validation.
- Persistent storage for customers, products, and invoice history.
- User accounts and secure authentication.
- Subscription management and payment integration, including an M-Pesa-compatible payment flow.
- Deployment as an online SaaS application.

These are development goals, not claims that the features are already available.

## Contributing

This is a personal learning and portfolio project. Suggestions and constructive feedback are welcome.

To contribute:

1. Fork the repository.
2. Create a feature branch.
3. Make and test your changes.
4. Open a pull request describing the improvement.

## Disclaimer

This project is under active development and may not yet be suitable for production use. Before using it for real business records, test invoice calculations, PDF output, currency conversions, data handling, and security carefully.

## Author

**Muturi Peter**

- GitHub: `https://github.com/muturi-peter`
- LinkedIn: `https://www.linkedin.com/in/peter-muturi-318011382/`
