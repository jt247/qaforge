# Private local configuration
Copy templates/identity.example.json to local/identity.json. Populate the dedicated Gmail address and test phone locally or provide those two values in the conversation for local configuration. Do not provide account passwords, OTPs, or full card data in chat.
Sign in to Gmail through your browser when needed; no Gmail connector is required by the scaffold. Aliases route into one inbox but may be normalized or rejected by an application. Review account limits before bulk creation. The lab does not automatically read Gmail yet.
Use local product secret files or a password manager for credentials and payment test details. Never reuse a real bank card. Store browser authentication states here if needed; treat them as credentials.
