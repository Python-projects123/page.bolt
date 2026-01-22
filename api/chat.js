export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "POST only" });
  }

  try {
    const { messages } = req.body;

    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: "Invalid messages array" });
    }

    // Build a simple chat-style prompt
    const prompt = messages.map(m => {
      if (m.role === "system") return `System: ${m.content}`;
      if (m.role === "user") return `User: ${m.content}`;
      if (m.role === "assistant") return `Assistant: ${m.content}`;
      return "";
    }).join("\n") + "\nAssistant:";

    const hfRes = await fetch(
      "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-0.5B-Instruct",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${process.env.HF_API_TOKEN}`,
        },
        body: JSON.stringify({
          inputs: prompt,
          parameters: {
            max_new_tokens: 220,
            temperature: 0.4,
            return_full_text: false
          }
        })
      }
    );

    if (!hfRes.ok) {
      const errText = await hfRes.text();
      return res.status(500).json({ error: errText });
    }

    const data = await hfRes.json();

    let text = "";
    if (Array.isArray(data) && data[0]?.generated_text) {
      text = data[0].generated_text;
    }

    return res.status(200).json({ text: text || "(No output.)" });

  } catch (err) {
    console.error("API error:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
}
