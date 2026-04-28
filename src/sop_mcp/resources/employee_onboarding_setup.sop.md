---
name: employee_onboarding_setup
description: 'This SOP defines the steps for onboarding a new employee, covering the
  initial setup tasks: obtaining the employee''s name from the HR partner, registering
  an alias in IT systems, sending the new empl…'
version: 1
owner: HR Department
stage: preprod
---

# Standard Operating Procedure: Employee Onboarding Setup

**Document ID**: employee_onboarding_setup
**Version**: 1
**Effective Date**: 2026-02-18
**Last Reviewed**: 2026-02-18
**Process Owner**: HR Department
**Author**: Kiro

---

## Overview

This SOP defines the steps for onboarding a new employee, covering the initial setup tasks: obtaining the employee's name from the HR partner, registering an alias in IT systems, sending the new employee an email with alias selection details, and providing a hardware selection list.

## Scope

**Included**:
- Retrieving new employee information from the HR department
- Registering an alias at IT
- Sending an email to the new employee with alias selection instructions
- Sending a hardware selection list to the new employee

**Excluded**:
- Employee training and orientation programs
- Access provisioning beyond alias registration
- Ongoing HR processes (payroll, benefits enrollment)
- Physical workspace setup

## Definitions

- **Alias**: A unique username/identifier assigned to the employee in IT systems
- **HR Partner**: The HR department contact responsible for providing new employee details
- **Hardware Selection List**: A catalog of available equipment the new employee can choose from

## Roles and Responsibilities

- **HR Partner**: Provides new employee name and details, initiates the onboarding process
- **IT Administrator**: Registers the alias, sends alias selection email, sends hardware list
- **New Employee**: Selects alias preference and hardware from provided options

## Prerequisites

- Access to the HR employee records system
- Access to the IT alias registration system
- Access to the company email system
- Access to the hardware catalog/inventory

## Parameters

- `employee_name`: Full name of the new employee (provided by HR)
- `hr_partner_name`: Name of the HR department partner handling the onboarding
- `employee_email`: Personal or temporary email address for initial contact
- `start_date`: The employee's planned start date

---

### Step 1: Obtain New Employee Information from HR Partner

**Objective**: Retrieve the new employee's details from the HR department partner.

**Actions**:
1. Contact the HR department partner assigned to the new hire
2. Request the new employee's full name, personal email address, planned start date, department, and job title
3. Confirm the information is accurate and complete

**Responsible Role**: IT Administrator

**Tools/Systems**: HR employee records system, email or messaging platform

**Decision Points**:
- If the HR partner is unavailable, escalate to the HR department manager
- If any required information is missing, request it before proceeding to the next step

**Requirements**:
- You MUST obtain the employee's full name, personal email, and start date before proceeding
- You MUST confirm the information accuracy with the HR partner
- You SHOULD obtain the department name and job title for hardware selection purposes
- You SHOULD document the HR partner's name for audit trail
- You MAY request additional information such as preferred name or accessibility needs

**Expected Output**: Provide the following details for the new employee:
- Full name (first and last)
- Personal/temporary email address
- Planned start date (YYYY-MM-DD)
- Department name
- Job title
- HR partner name who provided the information

---

### Step 2: Register an Alias at IT

**Objective**: Create a unique alias/username for the new employee in the IT system.

**Actions**:
1. Log in to the IT alias registration system
2. Generate a proposed alias based on the employee's name (e.g., first initial + last name)
3. Check that the alias is not already taken
4. If the alias is taken, generate an alternative (e.g., append a number or use middle initial)
5. Register the alias in the system

**Responsible Role**: IT Administrator

**Tools/Systems**: IT alias registration system

**Decision Points**:
- If the preferred alias is already taken, try variations: first initial + middle initial + last name, or first name + last initial
- If all standard variations are taken, flag for manual review

**Requirements**:
- You MUST verify the alias is unique before registering it
- You MUST register the alias in the IT system before sending any communication to the employee
- You MUST follow the alias naming convention (first initial + last name)
- You SHOULD attempt at least 3 alias variations before flagging for manual review
- You MAY reserve the alias temporarily while awaiting employee confirmation

**Expected Output**: Provide the following alias registration details:
- Registered alias (e.g., jsmith)
- Alias format used (e.g., first initial + last name)
- Registration status (REGISTERED / PENDING / CONFLICT)
- If CONFLICT: list of attempted aliases and the final registered alias
- Registration timestamp (YYYY-MM-DD HH:MM)

---

### Step 3: Send Alias Selection Email to New Employee

**Objective**: Notify the new employee of their alias options and allow them to confirm or request changes.

**Actions**:
1. Compose an email to the new employee's personal/temporary email address
2. Include the registered alias and any alternative options
3. Provide instructions on how to confirm or request a different alias
4. Set a response deadline (within 3 business days of the email)
5. Send the email

**Responsible Role**: IT Administrator

**Tools/Systems**: Company email system

**Decision Points**:
- If the employee requests a different alias, return to Step 2 to check availability and register the new alias
- If no response is received within 3 business days, send a follow-up reminder
- If no response after the reminder, proceed with the originally registered alias

**Requirements**:
- You MUST send the email to the employee's personal/temporary email address
- You MUST include the registered alias and instructions for requesting changes
- You MUST set a response deadline of 3 business days
- You SHOULD include at least one alternative alias option
- You SHOULD send a follow-up reminder if no response is received by the deadline
- You MAY include a welcome message and general onboarding information in the email

**Expected Output**: Provide the following email details:
- Recipient email address
- Email subject line
- Alias options included in the email
- Response deadline date (YYYY-MM-DD)
- Email sent status (SENT / FAILED)
- If FAILED: error description

---

### Step 4: Send Hardware Selection List to New Employee

**Objective**: Provide the new employee with a list of available hardware to choose from.

**Actions**:
1. Retrieve the current hardware catalog/inventory list appropriate for the employee's role and department
2. Compose an email to the new employee's personal/temporary email address
3. Include the hardware selection list with available options (laptop model, monitor, peripherals)
4. Provide instructions on how to submit their hardware selection
5. Set a selection deadline (within 5 business days of the email)
6. Send the email

**Responsible Role**: IT Administrator

**Tools/Systems**: Company email system, hardware inventory/catalog system

**Decision Points**:
- If certain hardware items are out of stock, note the estimated restock date or offer alternatives
- If the employee's role requires specialized hardware, consult with the department manager for approval
- If no response is received within 5 business days, send a follow-up reminder

**Requirements**:
- You MUST send the hardware list appropriate for the employee's role and department
- You MUST include instructions on how to submit the hardware selection
- You MUST set a selection deadline of 5 business days
- You SHOULD include all available categories (laptop, monitor, peripherals)
- You SHOULD note any out-of-stock items with estimated availability
- You MAY include recommended configurations based on the employee's role

**Expected Output**: Provide the following hardware email details:
- Recipient email address
- Email subject line
- Number of hardware options included
- Categories of hardware offered (e.g., laptop, monitor, keyboard, mouse)
- Selection deadline date (YYYY-MM-DD)
- Email sent status (SENT / FAILED)
- If FAILED: error description

---

## Troubleshooting

| Problem                                  | Possible Cause                     | Solution                                                                 |
| ---------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------ |
| HR partner does not respond              | Partner is on leave or unavailable | Escalate to HR department manager                                        |
| Alias already taken                      | Common name collision              | Try variations: middle initial, first name + last initial, append number |
| Email to new employee bounces            | Incorrect personal email address   | Contact HR partner to verify the email address                           |
| Hardware catalog unavailable             | System maintenance or outage       | Retry after 1 hour; if persistent, contact IT support                    |
| Employee does not respond to alias email | Email went to spam or was missed   | Send follow-up reminder; try alternate contact method via HR partner     |
| Employee requests unavailable hardware   | Item out of stock                  | Provide estimated restock date and offer alternatives                    |

## Best Practices

- Complete all onboarding steps at least 5 business days before the employee's start date
- Keep a checklist of completed steps for each new employee for audit purposes
- Batch onboarding tasks when multiple employees start on the same date
- Maintain an up-to-date hardware catalog to avoid delays

## Contact Information

- **Process Owner**: HR Department — hr-onboarding@company.com
- **IT Support**: IT Help Desk — it-helpdesk@company.com
- **Hardware Requests**: IT Procurement — it-procurement@company.com

---

## Revision History

| Version | Date       | Author | Changes         | Approved By   |
| ------- | ---------- | ------ | --------------- | ------------- |
| 1       | 2026-02-18 | Kiro   | Initial release | HR Department |
