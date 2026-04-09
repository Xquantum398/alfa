Dockerized M3U8 Proxy<br>

A lightweight proxy server based on Flask and Requests, designed to:<br>

📥 Download and edit .m3u / .m3u8 streams<br>
🔁 Proxy .ts segments, keeping custom headers<br>
🚫 Overcome restrictions like Referer, User-Agent, etc.<br>
🐳 Be easily dockerizable on any machine or server<br><br>


🤗 Deploy to HuggingFace<br>

Remember to do a factory rebuild to update the proxy if there are updates!<br>

Create a new Space<br>
Choose any name and set Docker as type<br>
Leave Public and create the Space<br>
Go to the top right → ⋮ → Files → upload Dockerfile<br>
Finally go to ⋮ → Embed this Space to get the Direct URL<br>
How to use: https://your.hugging.hf.space/http://video.url.here.m3u8<br>
OR https://your.hugging.hf.space/?url=http://video.url.here.m3u8


☁️ <dev>Deploy to Render TESTING</dev><br>

Go to Projects → Deploy a Web Service → Public Git Repo<br>
Enter the repo: https://github.com/nzo66/tvproxy → Connect<br>
Give it a name of your choice<br>
Set Instance Type to Free<br>
Click on Deploy Web Service
