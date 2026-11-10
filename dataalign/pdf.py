"""HTML -> PDF through a Gotenberg container (docker compose service). Not exercised in the build sandbox."""
import urllib.request, uuid

def html_to_pdf(html_text, out_path, host="http://localhost:3000"):
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"index.html\"\r\n"
            f"Content-Type: text/html\r\n\r\n{html_text}\r\n--{b}--\r\n").encode("utf-8")
    req = urllib.request.Request(host + "/forms/chromium/convert/html", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(out_path, "wb").write(r.read())
