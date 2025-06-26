async function sendMessage() {
  const input = document.getElementById("user-input");
  const message = input.value.trim();
  if (!message) return;

  const chatWindow = document.getElementById("chat-window");
  const userMsgDiv = document.createElement("div");
  userMsgDiv.className = "mb-2 text-right text-blue-600";
  userMsgDiv.textContent = "You: " + message;
  chatWindow.appendChild(userMsgDiv);

  input.value = "";

  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message })
  });

  const data = await response.json();

  const botMsgDiv = document.createElement("div");
  botMsgDiv.className = "mb-2 text-gray-600";
  botMsgDiv.textContent = "Bot: " + data.reply;
  chatWindow.appendChild(botMsgDiv);

  chatWindow.scrollTop = chatWindow.scrollHeight;
}
