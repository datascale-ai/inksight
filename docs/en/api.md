# API Reference

Core endpoints include:

- firmware release query and download
- device config get/save
- preview and render history
- auth, claim, and membership management

Most endpoints return JSON; firmware endpoints may return binary streams.

For protected endpoints, provide either:

- user auth token/session
- device token (`X-Device-Token`) when applicable
