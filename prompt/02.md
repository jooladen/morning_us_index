 정직 보고 — 요구사항 충돌 발견 (먼저 짚고 갑니다)

  "MCP Tool로 뉴스 검색" 부분이 GitHub Actions cron 환경에서는 그대로 동작하지 않습니다.

  - 🟢  초딩용: MCP는 "내가 Claude랑 대화할 때만 쓸 수 있는 도구"예요. 새벽 6시에 컴퓨터가 자동으로 돌아갈 때는 그      
  도구가 없어요. 그래서 다른 방법으로 뉴스를 가져와야 해요.
  - 🔵 개발자용: MCP(Model Context Protocol)는 Claude Code/Claude Desktop 같은 클라이언트가 stdio/SSE로 서버에 연결되어
   있을 때만 호출 가능. GitHub Actions 헤드리스 cron 러너는 MCP 클라이언트가 없으므로 mcp__* 도구를 직접 쓸 수 없음.   

  → 실제 가능한 대안: ① Gemini Grounding with Google Search (Gemini API에 내장된 검색 — 가장 자연스러움) ② Anthropic   
  web_search 도구 (Claude API tool use) ③ NewsAPI / Tavily / Perplexity API ④ yfinance Ticker.news + RSS (Yahoo Finance   / Reuters / Bloomberg)

---------------------------------
일단 mcp와 ai사용 등...분석은 phase로 구분해서    
     나중에 하는걸로 보류해주고..지수만 슬랙으로 매일 6시에 내 컴퓨터를 꺼도 항상 동작하도록 할수 있게 해줘.