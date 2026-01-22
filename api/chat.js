export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "POST only" });
  }

  try {
    const { messages } = req.body;

    if (!Array.isArray(messages)) {
      return res.status(400).json({ error: "messages must be an array" });
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
          Authorization: `Bearer ${process.env.HF_API_TOKEN}`
        },
        body: JSON.stringify({
          inputs: prompt,
          parameters: {
            max_new_tokens: 120,
            temperature: 0.4,
            return_full_text: false
          }
        })
      }
    );

    const raw = await hfRes.text();

    if (!hfRes.ok) {
      return res.status(500).json({ error: raw });
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      return res.status(500).json({ error: raw });
    }

    const text = data?.[0]?.generated_text || "(no output)";

    res.status(200).json({ text });

  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
}
