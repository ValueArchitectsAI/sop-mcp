---
name: employee_onboarding_setup
description: 'Onboarding a new employee: obtain details from HR, register an alias in IT, send an alias selection email, and send a hardware selection list.'
version: 1
owner: HR Department
stage: preprod
---

# Standard Operating Procedure: Employee Onboarding Setup

## Overview
Onboarding a new employee, covering the initial setup tasks: obtaining the employee's name from the HR partner, registering an alias in IT systems, sending the new employee an email with alias selection details, and providing a hardware selection list.

## Steps

### Step 1: Obtain New Employee Information from HR Partner

**Objective**: Retrieve the new employee's details from the HR department partner.

**Actions**:
1. Contact the HR department partner assigned to the new hire
2. Request the new employee's full name, personal email address, planned start date, department, and job title
3. Confirm the information is accurate and complete
4. If the HR partner is unavailable, escalate to the HR department manager
5. If any required information is missing, request it before proceeding

**Requirements**:
- You MUST obtain the employee's full name, personal email, and start date before proceeding
- You MUST confirm the information accuracy with the HR partner
- You SHOULD obtain the department name and job title for hardware selection purposes
- You SHOULD document the HR partner's name for audit trail
- You MAY request additional information such as preferred name or accessibility needs

**Expected Output**: Full name, personal email, start date (YYYY-MM-DD), department, job title, HR partner name.

**Time Estimate**: 15-30 minutes

---

### Step 2: Register an Alias at IT

**Objective**: Create a unique alias for the new employee in the IT system.

**Actions**:
1. Log in to the IT alias registration system
2. Generate a proposed alias based on the employee's name (e.g., first initial + last name)
3. Check that the alias is not already taken
4. If the alias is taken, generate an alternative (e.g., append a number or use middle initial)
5. Register the alias in the system

**Requirements**:
- You MUST verify the alias is unique before registering it
- You MUST register the alias before sending any communication to the employee
- You MUST follow the alias naming convention (first initial + last name)
- You SHOULD attempt at least 3 alias variations before flagging for manual review
- You MAY reserve the alias temporarily while awaiting employee confirmation

**Expected Output**: Registered alias, alias format used, registration status (REGISTERED / PENDING / CONFLICT). If CONFLICT, list of attempted aliases and the final registered alias, plus registration timestamp (YYYY-MM-DD HH:MM).

**Time Estimate**: 10-15 minutes

---

### Step 3: Send Alias Selection Email to New Employee

**Objective**: Notify the new employee of their alias options and allow them to confirm or request changes.

**Actions**:
1. Compose an email to the new employee's personal/temporary email address
2. Include the registered alias and at least one alternative option
3. Provide instructions on how to confirm or request a different alias
4. Set a response deadline of 3 business days
5. Send the email
6. If the employee requests a different alias, return to Step 2
7. If no response after the deadline, send a follow-up reminder; otherwise proceed with the registered alias

**Requirements**:
- You MUST send the email to the employee's personal/temporary email address
- You MUST include the registered alias and instructions for requesting changes
- You MUST set a response deadline of 3 business days
- You SHOULD include at least one alternative alias option
- You SHOULD send a follow-up reminder if no response is received by the deadline
- You MAY include a welcome message and general onboarding information

**Expected Output**: Recipient email, subject line, alias options included, response deadline (YYYY-MM-DD), sent status (SENT / FAILED). If FAILED, error description.

**Time Estimate**: 15-20 minutes

---

### Step 4: Send Hardware Selection List to New Employee

**Objective**: Provide the new employee with a list of available hardware to choose from.

**Actions**:
1. Retrieve the current hardware catalog appropriate for the employee's role and department
2. Compose an email with the hardware selection list (laptop, monitor, peripherals)
3. Note any out-of-stock items with estimated restock dates
4. Provide instructions on how to submit the hardware selection
5. Set a selection deadline of 5 business days
6. Send the email

**Requirements**:
- You MUST send the hardware list appropriate for the employee's role and department
- You MUST include instructions on how to submit the hardware selection
- You MUST set a selection deadline of 5 business days
- You SHOULD include all available categories (laptop, monitor, peripherals)
- You SHOULD note any out-of-stock items with estimated availability
- You MAY include recommended configurations based on the employee's role

**Expected Output**: Recipient email, subject line, number of hardware options, categories offered, selection deadline (YYYY-MM-DD), sent status (SENT / FAILED). If FAILED, error description.

**Time Estimate**: 15-20 minutes
