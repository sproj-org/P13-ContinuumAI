# P13: ContinuumAI — Sprint 1 Summary

This sprint was structured into **three major phases**, each contributing to the evolution of our system from a prototype into an MCP-driven, generalizable sales analytics agent.

---

## **1. Extending the Prototype & Implementing Sprint 1 Use Cases**

All work for this phase is located in the **`Code`** directory.

- We carried forward the initial prototype and manually implemented the Sprint 1 use cases (as listed in the project plan on GitHub).
- Separate READMEs for **frontend** and **backend** include detailed instructions for running the system locally.
- Since this work represents the functional baseline for Sprint 1, we preserved it and also deployed it for demonstration purposes.  
- **Deployed version:** `xyz.com`

---

## **2. Research Phase — Solving the “Unknown Schema” Problem**

This was the most critical part of Sprint 1.

### **The problem**
Our system performed well only when the input datasets aligned perfectly with our expectations — meaning:
- All required columns were present  
- Column names matched exactly what our functions expected  
- Schema was predictable  

To generalize the system for **any arbitrary dataset**, we needed a way to dynamically understand:
- Missing or mismatched columns  
- Different naming conventions  
- Varying schema structures  
- Additional or irrelevant columns  

### **Our research**
Over ~2 weeks, we explored multiple approaches to solve this schema-uncertainty challenge (all experimental work is inside the **`Research Work`** folder).

### **The solution**
We adopted **Model Context Protocol (MCP)** — a unified protocol that allows LLM agents to interact with tools and data using standardized formats for:
- Inputs  
- Outputs  
- Schemas  
- Errors  
- Capabilities  

MCP essentially allows the LLM to **understand the data before acting on it**, which solves our schema-related issues.

---

## **3. Implementing MCP in Our System**

This was the final phase of Sprint 1.

- We began transitioning from manual Python-function workflows to a fully MCP-driven architecture using **Vizro MCP**.
- During implementation, we discovered that integrating MCP into the old codebase created conflicts because of fundamental differences in design.
- As a result, we started building a **new MCP-based Sales Agent from scratch**, implementing most of the core functionality during this sprint.

All implementation work for this phase is inside the **`Vizro Conversion`** folder and will be continued in Sprint 2.

---

## **Additional Deliverables**

The following documents have been updated to reflect the new MCP-based architecture:

- Updated **Project Plan** (GitHub)  
- Updated **Threat Modeling Document**  
- Updated **System Architecture**  

All updates align with the new Vizro MCP Sales Agent design.

---
