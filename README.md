# EGP-CDA
# EGP-CDA Procurement Dashboard

A dynamic, front-end data visualization dashboard for the Chittagong Development Authority (CDA). This project tracks, parses, and visualizes e-GP (National e-Government Procurement) contract data to provide transparent insights into infrastructure spending in the Chattogram region.

## Features
* **Top Contracts by Value:** A bar chart visualizing the top 10 highest-value awarded contracts and their respective contractors.
* **Procurement Methods:** A breakdown of how contracts are procured (e.g., Open Tendering Method - OTM).
* **Funding Sources:** A look at where the budget comes from (Own Funds, Development Aid, etc.).

## Tech Stack
* **HTML/CSS/JavaScript:** Core structure and styling.
* **Chart.js:** Used for rendering responsive, interactive graphs.
* **Fetch API:** Asynchronously loads local JSON data.

## How to Run Locally
Because this project uses the JavaScript `fetch()` API to load the `eprocure_contracts_combined_CDA.json` file, you cannot simply double-click `index.html` to view it (due to browser CORS security policies). 

To run it locally:
1. Open the project folder in your terminal.
2. Run a local web server. For example, if you have Python installed:
   ```bash
   python -m http.server 8000
