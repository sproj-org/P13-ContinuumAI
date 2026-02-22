# Oracle Kubernetes Engine (OKE) Setup Guide

> **For:** Setting up OKE cluster for ContinuumAI project
> **Time Required:** ~20-30 minutes

---

## Overview

You need to create a Kubernetes cluster on Oracle Cloud so we can deploy our app. After you're done, you'll share some credentials with me.

---

## Step 1: Login to Oracle Cloud

1. Go to https://cloud.oracle.com
2. Login with your Oracle Cloud account

---

## Step 2: Create a Compartment

A compartment is like a folder to organize resources.

1. Click the **☰ hamburger menu** (top left)
2. Go to **Identity & Security** → **Compartments**
3. Click **Create Compartment**
4. Fill in:
   - **Name:** `ContinuumAI`
   - **Description:** `Resources for ContinuumAI app`
   - **Parent Compartment:** Leave as root
5. Click **Create Compartment**

---

## Step 3: Create a Virtual Cloud Network (VCN)

The VCN provides networking for the cluster.

1. Click **☰ Menu** → **Networking** → **Virtual Cloud Networks**
2. Make sure **Compartment** dropdown (left sidebar) shows `ContinuumAI`
3. Click **Start VCN Wizard**
4. Select **Create VCN with Internet Connectivity** → Click **Start VCN Wizard**
5. Fill in:
   - **VCN Name:** `continuum-vcn`
   - **Compartment:** `ContinuumAI`
   - Leave everything else as default
6. Click **Next** → Review → **Create**
7. Wait for it to complete, then click **View VCN**

---

## Step 4: Create the Kubernetes Cluster

1. Click **☰ Menu** → **Developer Services** → **Kubernetes Clusters (OKE)**
2. Make sure **Compartment** dropdown shows `ContinuumAI`
3. Click **Create Cluster**
4. Select **Quick Create** → Click **Submit**
5. Fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `continuum-cluster` |
| **Compartment** | `ContinuumAI` |
| **Kubernetes Version** | Latest available (e.g., v1.28.2) |
| **Kubernetes API Endpoint** | **Public Endpoint** ⚠️ IMPORTANT |
| **Node Type** | Managed |
| **Shape** | `VM.Standard.E4.Flex` or `VM.Standard.A1.Flex` (free tier) |
| **OCPUs** | 1 |
| **Memory (GB)** | 6 |
| **Number of Nodes** | 2 (or 1 if limited resources) |

6. Click **Next** → Review the summary
7. Click **Create Cluster**
8. **Wait 10-15 minutes** for the cluster status to change to **Active**

---

## Step 5: Generate API Keys

I need these keys to connect to your cluster from GitHub Actions.

1. Click your **Profile Icon** (top right corner) → **User Settings**
2. Scroll down to **Resources** section → Click **API Keys**
3. Click **Add API Key**
4. Select **Generate API Key Pair**
5. Click **Download Private Key** → Save the `.pem` file securely
6. Click **Add**
7. **IMPORTANT:** A popup will show "Configuration File Preview" - **COPY ALL OF THIS TEXT**

The preview looks like this:
```
[DEFAULT]
user=ocid1.user.oc1..aaaaaaaxxxxx
fingerprint=12:34:56:78:90:ab:cd:ef:12:34:56:78:90:ab:cd:ef
tenancy=ocid1.tenancy.oc1..aaaaaaaxxxxx
region=us-ashburn-1
key_file=~/.oci/oci_api_key.pem
```

---

## Step 6: Get the Cluster OCID

1. Go to **☰ Menu** → **Developer Services** → **Kubernetes Clusters (OKE)**
2. Click on `continuum-cluster`
3. On the cluster details page, find **OCID** 
4. Click **Copy** next to the OCID

---

## What to Send Back to Me

Please send me these **6 things** securely (via private message, NOT in any public channel):

### 1. Configuration Values (from Step 5)
```
User OCID: ocid1.user.oc1..xxxxx
Fingerprint: xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
Tenancy OCID: ocid1.tenancy.oc1..xxxxx
Region: us-ashburn-1
```

### 2. Private Key File
- The `.pem` file you downloaded in Step 5
- Send the **entire contents** of this file

### 3. Cluster OCID (from Step 6)
```
Cluster OCID: ocid1.cluster.oc1.xxx.xxxxx
```

---

## Checklist Before Sending

- [ ] Cluster status is **Active** (not Creating or Updating)
- [ ] Cluster has **Public Endpoint** enabled
- [ ] You have all 6 values listed above
- [ ] Private key file is saved and ready to share

---

## Security Note

⚠️ **Keep these credentials private!** 
- Don't share them in public channels/repos
- Send them through secure/private channels only
- These allow access to your Oracle Cloud resources

---

## Questions?

If any step is unclear or you see an error, take a screenshot and send it to me!
