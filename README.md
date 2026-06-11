# Logix Component Manager

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![Rockwell Automation](https://img.shields.io/badge/Logix%20Designer-SDK-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A professional GUI utility for bulk-managing Studio 5000 Logix Designer components. This tool simplifies the process of migrating Programs, Add-On Instructions (AOIs), and User-Defined Types (UDTs) between `.ACD` project files using the Logix Designer SDK.

## ✨ Key Features

- **Smart Import:** Automatically identifies component types from `.L5X` files and handles naming collisions (Overwrite vs. Discard).
- **Batch Export:** Scan an existing project and select multiple components to export to XML simultaneously.
- **Indexed Copying:** A "Pro" feature—export a single component and automatically generate multiple indexed copies (e.g., export `Valve` once to create `Valve_1`, `Valve_2`, `Valve_3`).
- **Asynchronous Engine:** Uses a dedicated background event loop (`asyncio`) to ensure the UI never freezes, even when opening massive `.ACD` files.
- **L5X Inspection:** Deep-links into XML structures to ensure imports are placed in the correct project controller folders.

## 🛠️ Prerequisites

*   **Studio 5000 Logix Designer SDK:** This application requires a valid installation of the Rockwell Automation Logix Designer SDK.
*   **Python 3.9+**
*   **Logix Project Files:** Supports `.ACD` (Project) and `.L5X` (XML) formats.

## 🚀 Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Logix-Component-Manager.git
   cd Logix-Component-Manager