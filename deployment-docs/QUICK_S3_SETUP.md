# ⚡ Quick S3 Setup (5 Minutes)

## Step 1: Create Bucket (2 min)

1. Go to: https://s3.console.aws.amazon.com/
2. Click **"Create bucket"**
3. **Name**: `nfl-predictions-chatbot` (or any unique name)
4. **Region**: `us-east-1`
5. **UNCHECK** "Block all public access" ⚠️
6. Check the acknowledgment box
7. Click **"Create bucket"**

---

## Step 2: Upload File (1 min)

1. Click your bucket name
2. Click **"Upload"**
3. Drag `chatbot-interface.html` into the upload area
4. Click **"Upload"**

---

## Step 3: Make Public (1 min)

1. Go to **"Permissions"** tab
2. Scroll to **"Bucket policy"**
3. Click **"Edit"**
4. Paste this (replace `YOUR-BUCKET-NAME`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
        }
    ]
}
```

5. Click **"Save changes"**

---

## Step 4: Enable Website (1 min)

1. Go to **"Properties"** tab
2. Scroll to **"Static website hosting"**
3. Click **"Edit"**
4. Select **"Enable"**
5. **Index document**: `chatbot-interface.html`
6. Click **"Save changes"**
7. **COPY THE WEBSITE URL** at the top (looks like: `http://nfl-predictions-chatbot.s3-website-us-east-1.amazonaws.com`)

---

## Step 5: Test! 🎉

Open the S3 website URL in your browser and try a prediction!

**That's it! Your chatbot is live on the internet!** 🚀


















