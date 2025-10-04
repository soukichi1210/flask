document.addEventListener('DOMContentLoaded', () => {
  const questionArea = document.getElementById('question-area');
  const optionArea = document.getElementById('option-buttons');
  const explanationArea = document.getElementById('explanation-area');
  const nextBtn = document.getElementById('next');
  const endBtn = document.getElementById('end');
  const loading = document.getElementById('loading');

  let currentCorrectAnswer = null;
  let selectedBtn = null;

  if (window.first_question) {
    const firstData = JSON.parse(window.first_question);
    renderResponse(firstData);
  }

  nextBtn.addEventListener('click', () => sendToServer('next'));
  endBtn.addEventListener('click', () => sendToServer('end'));

  async function sendAnswer(choiceNumber, btn) {
    selectedBtn = btn;
    const buttons = optionArea.querySelectorAll("button");
    buttons.forEach(b => b.disabled = true);
    await sendToServer(String(choiceNumber));
  }

  async function sendToServer(message) {
    loading.classList.remove("hidden");

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // ★ 10秒でタイムアウト

      const res = await fetch("/api/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!res.ok) throw new Error(`サーバーエラー: ${res.status}`);

      const data = await res.json();

      if (data.redirect) {
        setTimeout(() => {
          window.location.href = data.redirect;
        }, 2000);
        return;
      }

      let parsed;
      try {
        parsed = JSON.parse(data.reply);
      } catch (e) {
        showExplanation("博士", data.reply);
        return;
      }

      if (Array.isArray(parsed)) {
        parsed.forEach(item => renderResponse(item));
      } else {
        renderResponse(parsed);
      }

    } catch (err) {
      // ★ 通信エラー / タイムアウト時の処理
      showError(`通信エラーが発生しました。\n${err.message}`);
    } finally {
      loading.classList.add("hidden");
    }
  }

  function renderResponse(data) {
    if (data.type === "question") {
      questionArea.innerHTML = "";
      const qText = document.createElement("h2");
      qText.textContent = `第${data.question_number}問: ${data.question_text}`;
      questionArea.appendChild(qText);

      optionArea.innerHTML = "";
      explanationArea.innerHTML = "";
      currentCorrectAnswer = data.correct_answer;

      data.options.forEach(opt => {
        const btn = document.createElement("button");
        btn.className = "option-btn big-btn";
        btn.textContent = `${opt.number}. ${opt.text}`;
        btn.onclick = () => sendAnswer(opt.number, btn);
        optionArea.appendChild(btn);
      });

      nextBtn.classList.add("hidden");

    } else if (data.type === "evaluation") {
      const buttons = optionArea.querySelectorAll("button");
      if (selectedBtn) {
        if (data.result === "正解") {
          selectedBtn.style.backgroundColor = "#28a745";
        } else {
          selectedBtn.style.backgroundColor = "#dc3545";
          buttons.forEach(b => {
            if (b.textContent.startsWith(currentCorrectAnswer + ".")) {
              b.style.backgroundColor = "#28a745";
            }
          });
        }
      }
      buttons.forEach(b => (b.disabled = true));

      showExplanation("博士", `${data.result}\n${data.explanation}`);
      nextBtn.classList.remove("hidden");
    }
  }

  function showExplanation(speaker, text) {
    explanationArea.innerHTML = `
      <div class="chat-message">
        <b>${speaker}:</b><br>${text.replace(/\n/g, "<br>")}
      </div>
    `;
  }

  function showError(message) {
    questionArea.innerHTML = `
      <div style="color: red; font-weight: bold; text-align: center;">
        ${message.replace(/\n/g, "<br>")}
      </div>
      <button onclick="window.location.href='/'" style="margin-top:20px; padding:10px 20px; font-size:16px;">
        タイトルに戻る
      </button>
    `;
    optionArea.innerHTML = "";
    explanationArea.innerHTML = "";
    nextBtn.classList.add("hidden");
    endBtn.classList.add("hidden");
  }
});
