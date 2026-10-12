const questions = [
  {
    question: "HTML là gì?",
    answers: {
      a: "Ngôn ngữ đánh dấu",
      b: "Ngôn ngữ lập trình",
      c: "Cơ sở dữ liệu",
      d: "Hệ điều hành"
    },
    correct: "a"
  },
  {
    question: "CSS dùng để làm gì?",
    answers: {
      a: "Biên dịch chương trình",
      b: "Lưu trữ dữ liệu",
      c: "Tạo cơ sở dữ liệu",
      d: "Quản lý máy chủ",
      e: "Thiết kế giao diện"
    },
    correct: "e"
  },
  {
    question: "Java là gì?",
    answers: {
      a: "Hệ điều hành",
      b: "Ngôn ngữ lập trình",
      c: "Trình duyệt web",
      d: "Cơ sở dữ liệu"
    },
    correct: "b"
  },
  {
    question: "Từ khóa dùng để khai báo lớp trong Java là gì?",
    answers: {
      a: "class",
      b: "Class",
      c: "new",
      d: "object"
    },
    correct: "a"
  },
  {
    question: "Phương thức chính của chương trình Java là gì?",
    answers: {
      a: "start()",
      b: "run()",
      c: "main()",
      d: "execute()"
    },
    correct: "c"
  },
  {
    question: "Kiểu dữ liệu nào dùng để lưu số nguyên trong Java?",
    answers: {
      a: "double",
      b: "String",
      c: "boolean",
      d: "int"
    },
    correct: "d"
  },
  {
    question: "Từ khóa nào dùng để tạo đối tượng mới?",
    answers: {
      a: "class",
      b: "new",
      c: "this",
      d: "static"
    },
    correct: "b"
  },
  {
    question: "Lớp nào dùng để nhập dữ liệu từ bàn phím?",
    answers: {
      a: "Scanner",
      b: "Input",
      c: "Keyboard",
      d: "Reader"
    },
    correct: "a"
  },
  {
    question: "Java hỗ trợ tính chất OOP nào?",
    answers: {
      a: "Kế thừa",
      b: "Đóng gói",
      c: "Đa hình",
      d: "Tất cả đáp án trên"
    },
    correct: "d"
  },
  {
    question: "Ký hiệu dùng để kế thừa một lớp trong Java là gì?",
    answers: {
      a: "implements",
      b: "inherits",
      c: "extends",
      d: "super"
    },
    correct: "c"
  },
  {
    question: "Kiểu dữ liệu nào lưu giá trị đúng hoặc sai?",
    answers: {
      a: "char",
      b: "boolean",
      c: "String",
      d: "float"
    },
    correct: "b"
  }
];

let currentQuestion = 0;
let score = 0;
let answered = false;

const questionEl = document.getElementById("question");
const answersEl = document.getElementById("answers");
const resultEl = document.getElementById("result");
const nextBtn = document.getElementById("nextBtn");
const scoreBox = document.getElementById("scoreBox");

showQuestion();

function showQuestion() {
  answered = false;
  resultEl.textContent = "";
  nextBtn.style.display = "none";
  answersEl.innerHTML = "";

  // sáo trộn câu hỏi
  if(currentQuestion === 0)
   shuffleArray(questions);
  const q = questions[currentQuestion];
 
  questionEl.textContent = `Câu ${currentQuestion + 1}: ${q.question}`;

  const answers = disturbanceAnswer(q.answers); 

  let a = "a";
   
  for (const [key, value] of answers){
    //console.log(key);
    
    const btn = document.createElement("button");

    btn.value  = key;
    btn.className = "answer-btn";
    btn.textContent = a + ". "+value;
    btn.onclick = () => checkAnswer(btn, key);
    answersEl.appendChild(btn);
    a = String.fromCharCode(a.charCodeAt(0) + 1);
   }
}
function disturbanceAnswer(answers) {
    const result = Object.entries(answers);

    result.sort(() => Math.random() - 0.5);

    return result;
}

function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));

        [array[i], array[j]] = [array[j], array[i]];
    }

    return array;
}

function checkAnswer(button, key) {
  if (answered) return;

  answered = true;

  const q = questions[currentQuestion];
  const allButtons = document.querySelectorAll(".answer-btn");

  if (key === q.correct) {
    button.classList.add("correct");
    resultEl.textContent = "✅ Chính xác";
    score++;
  } else {
    button.classList.add("wrong");
    resultEl.textContent = "❌ Sai rồi";

    for (const btn of allButtons) {
      if (btn.value === q.correct) {
        btn.classList.add("correct");
      }
    }
  }

  allButtons.forEach(btn => btn.disabled = true);

  nextBtn.style.display = "inline-block";
}

nextBtn.onclick = () => {
  currentQuestion++;

  if (currentQuestion < questions.length) {
    showQuestion();
  } else {
    document.getElementById("quiz").style.display = "none";

    scoreBox.innerHTML = `
      <h2>Kết quả</h2>
      <p>Bạn đúng <b>${score}/${questions.length}</b> câu</p>
      <button onclick="location.reload()">
        Chơi lại
      </button>
    `;
  }
};