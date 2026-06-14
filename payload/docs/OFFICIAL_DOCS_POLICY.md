[Overview](../README.md) | [Architecture](ARCHITECTURE.md) | [CLI](CLI.md) | [Tools](TOOLS.md) | [Governance](GOVERNANCE.md)

# Official Documentation Policy

This project treats official vendor documentation as mandatory input for every external integration.

## Rule

Before implementing, debugging, or changing any integration with an external API, SDK, CLI, OAuth provider, webhook, cloud service, or vendor endpoint, the agent must verify the current official documentation.

Do not rely only on:

- model memory;
- old examples from this repository;
- community snippets;
- blog posts;
- Stack Overflow answers;
- previously working endpoint paths;
- assumptions from similar APIs.

## Required Workflow

1. Identify the external system involved.
2. Find the current official documentation for the exact feature, endpoint, auth flow, SDK, or API version.
3. Compare the project implementation against that documentation.
4. Prefer the official endpoint, parameter names, scopes, headers, and response schema.
5. Record the documentation URL in the relevant project doc, issue, PR, or code comment when it explains a non-obvious integration decision.
6. If official documentation conflicts with current code, update the code or explicitly document why the project cannot follow it.

## Why This Exists

During the LinkedIn OAuth/OIDC setup, the project initially used an older profile endpoint:

```text
https://api.linkedin.com/v2/people/~:(id,localizedFirstName)?format=json
```

That endpoint failed for the OpenID Connect flow with:

```text
HTTP 400 ILLEGAL_ARGUMENT: Syntax exception in path variables
```

Checking the current official Microsoft/LinkedIn documentation showed that the correct OIDC member information endpoint is:

```text
https://api.linkedin.com/v2/userinfo
```

Official reference:

```text
https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
```

This policy exists to prevent stale integration knowledge from becoming implementation guidance.

## Minimum Standard For Future Integrations

Every integration issue should include:

- official documentation URL;
- auth method and required scopes/permissions;
- endpoint URLs or SDK methods used;
- relevant request parameters;
- expected success response shape;
- common failure modes observed during implementation.

If documentation cannot be accessed, mark the integration issue as blocked or proceed only with an explicit caveat in the issue notes.
