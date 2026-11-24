// ── MOCK DATA ──
// This data is temporary. Once your backend is ready,
// replace these with real Axios API calls.

export const SAMPLE_MESSAGES = [
  {
    id: 1,
    role: "user",
    content: "How does the authentication flow work in this repository?"
  },
  {
    id: 2,
    role: "ai",
    agent: "architect",
    sources: [
      { file: "app/auth/jwt.py",        lines: "12-45" },
      { file: "app/api/auth.py",         lines: "8-32"  },
      { file: "app/middleware/auth.py",  lines: "1-28"  },
    ],
    content: {
      sections: [
        {
          title: "Authentication Flow",
          text: "The repository uses JWT-based authentication with a 3-layer middleware approach. Here's the complete flow:"
        },
        {
          title: "1. Login Endpoint",
          text: "User credentials are sent to POST /auth/login. The AuthService validates against the database and generates a JWT token.",
          code: {
            file: "app/api/auth.py",
            lines: "8-24",
            content: `<span class="kw">@router</span>.post(<span class="str">"/auth/login"</span>)
<span class="kw">async def</span> <span class="fn">login</span>(credentials: LoginSchema, db: Session):
    <span class="cm"># Validate user credentials</span>
    user = auth_service.<span class="fn">validate_user</span>(
        db, credentials.email, credentials.password
    )
    <span class="kw">if not</span> user:
        <span class="kw">raise</span> HTTPException(status_code=<span class="str">401</span>)
    token = jwt_service.<span class="fn">generate_token</span>(user.id)
    <span class="kw">return</span> {<span class="str">"access_token"</span>: token}`
          }
        },
        {
          title: "2. JWT Generation",
          text: "Tokens are generated with a 24h expiry, using HS256 algorithm. The payload includes user ID and role.",
        }
      ]
    }
  },
  {
    id: 3,
    role: "user",
    content: "Where exactly is the JWT token generated and what is the secret key setup?"
  },
  {
    id: 4,
    role: "ai",
    agent: "explainer",
    sources: [
      { file: "app/auth/jwt.py",         lines: "15-38" },
      { file: "app/config/settings.py",  lines: "4-12"  },
    ],
    content: {
      sections: [
        {
          title: "JWT Generation",
          text: "The token generation happens in jwt.py. The secret key is loaded from environment variables via the config module.",
          code: {
            file: "app/auth/jwt.py",
            lines: "15-32",
            content: `<span class="kw">def</span> <span class="fn">generate_token</span>(user_id: <span class="fn">int</span>) -> <span class="fn">str</span>:
    <span class="cm">"""Generate a signed JWT token for the user"""</span>
    payload = {
        <span class="str">"sub"</span>: str(user_id),
        <span class="str">"exp"</span>: datetime.utcnow() + timedelta(hours=<span class="str">24</span>),
        <span class="str">"iat"</span>: datetime.utcnow()
    }
    <span class="kw">return</span> jwt.<span class="fn">encode</span>(
        payload,
        settings.SECRET_KEY,
        algorithm=<span class="str">"HS256"</span>
    )`
          }
        }
      ]
    }
  }
];

export const FILE_TREE = [
  { name: "app/",             type: "folder", indent: 0 },
  { name: "auth/",            type: "folder", indent: 1 },
  { name: "jwt.py",           type: "file",   lang: "py", indent: 2 },
  { name: "service.py",       type: "file",   lang: "py", indent: 2 },
  { name: "api/",             type: "folder", indent: 1 },
  { name: "auth.py",          type: "file",   lang: "py", indent: 2 },
  { name: "chat.py",          type: "file",   lang: "py", indent: 2 },
  { name: "rag/",             type: "folder", indent: 1 },
  { name: "pipeline.py",      type: "file",   lang: "py", indent: 2 },
  { name: "retriever.py",     type: "file",   lang: "py", indent: 2 },
  { name: "agents/",          type: "folder", indent: 1 },
  { name: "explainer.py",     type: "file",   lang: "py", indent: 2 },
  { name: "debugger.py",      type: "file",   lang: "py", indent: 2 },
  { name: "bug_finder.py",    type: "file",   lang: "py", indent: 2 },
  { name: "architect.py",     type: "file",   lang: "py", indent: 2 },
  { name: "README.md",        type: "file",   lang: "md", indent: 0 },
];

// Agent routing — matches your backend agents exactly
export const AGENT_LABELS = {
  explainer: "Code Explainer",
  debugger:  "Debugger",
  bugfinder: "Bug Finder",
  architect: "Architect"
};

// Which keywords trigger which agent
export function detectAgent(text) {
  const lower = text.toLowerCase();
  if (lower.includes("bug") || lower.includes("issue") || lower.includes("problem"))
    return "bugfinder";
  if (lower.includes("debug") || lower.includes("error") || lower.includes("fix"))
    return "debugger";
  if (lower.includes("architecture") || lower.includes("flow") ||
      lower.includes("structure") || lower.includes("summarize"))
    return "architect";
  return "explainer";
}