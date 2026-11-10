const http = require("http"), fs = require("fs"), path = require("path");
const root = path.join(__dirname, "preview");
http.createServer((req, res) => {
  const f = path.join(root, req.url === "/" ? "index.html" : path.normalize(req.url).replace(/^(\.\.[\/\\])+/, ""));
  fs.readFile(f, (err, buf) => { if (err) { res.writeHead(404); return res.end("not found"); } res.writeHead(200, {"Content-Type": f.endsWith(".html") ? "text/html; charset=utf-8" : "application/octet-stream"}); res.end(buf); });
}).listen(+(process.env.PORT || 4130), "127.0.0.1", () => console.log("serving on " + (process.env.PORT || 4130)));
