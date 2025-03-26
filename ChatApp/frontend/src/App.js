import React, { useState } from "react";
import axios from "axios";

function ChatApp() {
    const [username, setUsername] = useState("");
    const [messages, setMessages] = useState([]);
    const [response, setResponse] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [questionIndex, setQuestionIndex] = useState(0);
    const [demographicResponses, setDemographicResponses] = useState({});

    const questions = [
        "What is your age?",
        "What is your gender? (Male/Female/Other)",
        "What is your occupation?",
        "What country do you live in?"
    ];

    const analyzeUser = async () => {
        if (!username) return;
        setIsAnalyzing(true);

        try {
            const res = await axios.post("http://127.0.0.1:5000/predict", {
                username,
            });

            const analysisResult = res.data.depression === 1 ? "Likely Depressed" : "Not Depressed";
            setMessages([{ text: analysisResult, isResponse: true }]);
            setResponse(analysisResult);

            // Start the demographic questions
            askNextQuestion();
        } catch (error) {
            console.error("Error analyzing user:", error);
            setMessages([{ text: "Error analyzing user.", isResponse: true }]);
        }
    };

    const askNextQuestion = () => {
        if (questionIndex < questions.length) {
            setMessages(prevMessages => [...prevMessages, { text: questions[questionIndex], isResponse: true }]);
        }
    };

    const handleUserResponse = async (event) => {
        if (event.key === "Enter") {
            const userResponse = event.target.value.trim();
            if (!userResponse) return;

            setMessages(prevMessages => [...prevMessages, { text: userResponse, isResponse: false }]);

            const updatedResponses = { ...demographicResponses, [questions[questionIndex]]: userResponse };
            setDemographicResponses(updatedResponses);

            if (questionIndex < questions.length - 1) {
                setQuestionIndex(prevIndex => prevIndex + 1);
                setTimeout(askNextQuestion, 500);
            } else {
                // Send demographic data to the server
                await axios.post("http://127.0.0.1:5000/store_demographics", {
                    username,
                    ...updatedResponses
                });
                setMessages(prevMessages => [...prevMessages, { text: "Thank you! Your data has been saved.", isResponse: true }]);
                setIsAnalyzing(false);
            }

            event.target.value = ""; // Clear input field
        }
    };

    return (
        <div style={{ padding: "20px", maxWidth: "400px", margin: "auto" }}>
            <h2>Chatbot</h2>
            <input
                type="text"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                style={{ width: "100%", marginBottom: "10px" }}
                disabled={isAnalyzing}
            />
            <button onClick={analyzeUser} style={{ marginBottom: "10px" }} disabled={isAnalyzing}>Analyze</button>
            <div>
                {messages.map((msg, index) => (
                    <p key={index} style={{ background: msg.isResponse ? "#f8d7da" : "#ddd", padding: "5px", borderRadius: "5px" }}>
                        {msg.text}
                    </p>
                ))}
            </div>
            {isAnalyzing && questionIndex < questions.length && (
                <input
                    type="text"
                    placeholder="Your response..."
                    onKeyDown={handleUserResponse}
                    style={{ width: "100%", marginTop: "10px" }}
                />
            )}
        </div>
    );
}

export default ChatApp;
