# LAPS – Line Allocation & Planning System

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)
![Status](https://img.shields.io/badge/Status-Work%20In%20Progress-yellow)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📌 Overview

**LAPS (Line Allocation & Planning System)** is a production-focused web application designed for shopfloor supervisors and planners to convert:

> **Daily production plan → required manpower → operator-wise activity allocation**

The system uses **predefined activity time data**, **takt-based logic**, and a **fully explainable sequential allocation algorithm**.  
There is no AI, no black box, and no auto-rebalancing — only deterministic, auditable logic that can be trusted on the shopfloor.

This is a **decision-support calculator**, not an analytics dashboard.

---

## 🎯 Key Objectives

- Eliminate guesswork in manpower planning
- Standardize line balancing across multiple assembly lines
- Highlight overloads and underutilization before execution
- Provide fast, repeatable, and explainable results for daily use

---

## 🛠 Tech Stack

- **Backend:** Python 3.10+
- **Framework:** Flask (3.x compatible)
- **Database:** SQLite (local, simple, reliable)
- **Data Handling:** Pandas
- **Frontend:** HTML, Bootstrap 5, minimal JavaScript
- **Export:** Excel (.xlsx)
- **Hosting:** Local / Intranet

---

## 🗂 Application Modules

### 1️⃣ Line Master (One-Time Setup)

- Create and manage assembly lines
- Define activity sequences with standard time (seconds)
- Auto-calculate total work content
- Data stored in normalized SQLite tables

**Activity Master Structure:**
```
line_id
activity_seq_no
activity_text
time_sec
```

---

### 2️⃣ Daily Plan (Primary Screen)

- Enter production date and shift duration
- Input plan quantity per line
- Generate allocations on the same screen
- Supports multiple lines in a single run

**Calculated Outputs:**
- Shift time
- Takt time
- Total work content
- Required manpower
- Maximum station time

---

### 3️⃣ Operator-wise Allocation

Activities are allocated using a **sequential bucket-fill algorithm**.

| Operator | Activities | Total Time | Status |
|--------|-----------|-----------|--------|
| OP1 | Act 1–4 | 72s | 🟢 |
| OP2 | Act 5–7 | 80s | 🔴 |
| OP3 | Act 8–10 | 48s | 🟡 |

**Status Logic:**
- 🟢 ≤ Takt
- 🔴 > Takt (Overload)
- 🟡 < 60% of Takt (Underutilized)

---

## ⚙️ Core Calculation Logic

- **ShiftSeconds** = ShiftMinutes × 60  
- **Takt Time** = ShiftSeconds ÷ Plan Quantity  
- **Total Work Content** = Sum of all activity times  

**Manpower Calculation:**
```
theoretical_manpower = ceil(TotalWorkContent / Takt)
```

If overload exists:
- Increment manpower
- Recalculate allocation
- Repeat until:
  - Max operator time ≤ Takt  
  **OR**
  - Manpower equals number of activities

No auto-fixing or rearrangement is done — only alerts are shown.

---

## 🚨 Alerts & Review

- Overload alerts
- Underutilization alerts
- Imbalance visibility

The system highlights issues but **does not auto-correct**, keeping human judgment in control.

---

## 🔐 User Roles

### 👷 Admin
- Line Master
- Daily Plan & Allocation
- Export / Print
- Backup database

### 🧑‍💻 Developer
- All Admin features
- Restore database
- Reset passwords

Only two controlled roles — no role sprawl.

---

## 💾 Backup & Restore

- One-click SQLite database backup
- Developer-only restore option
- Designed for fast recovery in case of system failure

---

## 🧠 Design Philosophy

- Minimal daily input
- Maximum clarity in output
- Deterministic and explainable logic
- No unnecessary analytics
- Built for daily operational trust

---

## 📦 Project Status

**Work in Progress**

Core logic and MVP features are functional.  
Excel import/export, print-friendly A4 views, and advanced alerts are under active development.

---

## 🚀 Getting Started

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py

