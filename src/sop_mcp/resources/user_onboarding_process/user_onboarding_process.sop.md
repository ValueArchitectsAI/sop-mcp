---
name: user_onboarding_process
description: Standard process for onboarding new users to the organization's systems and tools with consistent access provisioning.
version: 1
owner: IT Operations Team
stage: preprod
---

# Standard Operating Procedure: User Onboarding Process

## Overview
Standard process for onboarding new users to the organization's systems and tools, ensuring consistent access provisioning and a smooth first-day experience.

## Steps

### Step 1: Create User Identity

**Objective**: Provision the new user's core identity in the organization's IAM system.

**Actions**:
1. Verify the hire confirmation and start date from HR
2. Create the user account in the identity provider (e.g. Okta, Azure AD)
3. Set a temporary password and configure MFA enrollment
4. Assign the user to the appropriate organizational unit

**Requirements**:
- You MUST verify HR confirmation before creating any accounts
- You MUST enforce MFA enrollment on first login
- You SHOULD use the naming convention: firstname.lastname
- You MAY create an alias if there is a naming conflict

**Expected Output**: User account created in the identity provider, temporary credentials generated, MFA enrollment pending.

**Time Estimate**: 15-20 minutes

---

### Step 2: Provision Application Access

**Objective**: Grant access to the tools and applications required for the user's role.

**Actions**:
1. Review the role-based access matrix for the user's position
2. Assign SSO application entitlements based on role
3. Create accounts in systems that don't support SSO
4. Verify access by confirming the user appears in each application's user list

**Requirements**:
- You MUST follow the principle of least privilege
- You MUST only grant access listed in the role-based access matrix
- You SHOULD document any exceptions to standard access
- You MAY grant temporary elevated access with manager approval and an expiry date

**Expected Output**: All role-required applications accessible via SSO, non-SSO accounts created and documented, access verification checklist completed.

**Time Estimate**: 20-30 minutes

---

### Step 3: Send Welcome Package and Verify

**Objective**: Deliver credentials and onboarding materials to the new user and confirm everything works.

**Actions**:
1. Send the welcome email with login instructions and temporary credentials
2. Include links to onboarding documentation and training materials
3. Schedule a 15-minute IT check-in for the user's first day
4. Verify the user can log in and access all provisioned applications

**Requirements**:
- You MUST send credentials through a secure channel (not plain email for passwords)
- You MUST verify access works before marking onboarding complete
- You SHOULD include a troubleshooting FAQ in the welcome package
- You MAY assign a buddy from the team for first-week support

**Expected Output**: Welcome email sent with secure credential delivery, first-day IT check-in scheduled, all access verified and onboarding marked complete.

**Time Estimate**: 15-20 minutes
