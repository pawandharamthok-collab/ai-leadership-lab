import urllib.request
import urllib.parse
import re

def search_the_web(query: str) -> str:
    """Searches the live public internet using DuckDuckGo and returns top search results and snippets."""
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://lite.duckduckgo.com/lite/',
            data=data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        
        # Extract snippets and titles
        snippets = re.findall(r"<td class='result-snippet'>(.*?)</td>", html, flags=re.DOTALL)
        titles = re.findall(r"class='result-link'>(.*?)</a>", html)
        links = re.findall(r"<a rel=\"nofollow\" href=\"(.*?)\" class='result-link'", html)
        if not links:
            links = re.findall(r"<a rel='nofollow' href='(.*?)' class='result-link'", html)

        results = []
        for i in range(min(4, len(snippets))):
            snippet_text = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            title_text = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else "Result"
            url_text = links[i] if i < len(links) else ""
            results.append(f"{i+1}. **{title_text}**\n   {snippet_text}\n   *Link:* {url_text}")

        if results:
            return "\n\n".join(results)
        return f"No results found for query: {query}"
    except Exception as e:
        return f"Error executing web search: {str(e)}"

if __name__ == "__main__":
    print(search_the_web("latest AWS Bedrock models"))
