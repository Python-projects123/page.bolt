export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "POST only" });
  }

  try {
    const { messages } = req.body;

    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: "Invalid messages array" });
    }

    const prompt =
      messages.map(m => `${m.role}: ${m.content}`).join("\n") +
      "\nassistant:";

    const hfRes = await fetch(
      "https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-0.5B-Instruct",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${process.env.HF_API_TOKEN}`
        },
        body: JSON.stringify({
          inputs: prompt,
          parameters: {
            max_new_tokens: 150,
            temperature: 0.4,
            return_full_text: false
          }
        })
      }
    );

    if (!hfRes.ok) {
      const err = await hfRes.text();
      return res.status(500).json({ error: err });
    }

    const data = await hfRes.json();
    const text = data?.[0]?.generated_text || "(no output)";

    res.status(200).json({ text });

  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
}

