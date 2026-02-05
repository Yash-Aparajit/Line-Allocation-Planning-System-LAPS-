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
