package com.ghostgpt.companion

import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var client: AgentClient
    private lateinit var chatRecycler: RecyclerView
    private lateinit var adapter: ChatAdapter
    private lateinit var inputField: EditText
    private lateinit var sendBtn: Button
    private lateinit var progressBar: ProgressBar
    private var currentJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val prefs = getSharedPreferences("ghostgpt", MODE_PRIVATE)
        val host = prefs.getString("host", "192.168.1.100") ?: "192.168.1.100"
        val port = prefs.getInt("port", 8765)
        client = AgentClient("http://$host:$port")

        chatRecycler = findViewById(R.id.chat_recycler)
        inputField = findViewById(R.id.input_field)
        sendBtn = findViewById(R.id.send_btn)
        progressBar = findViewById(R.id.progress_bar)

        adapter = ChatAdapter()
        chatRecycler.layoutManager = LinearLayoutManager(this).apply {
            stackFromEnd = true
        }
        chatRecycler.adapter = adapter

        sendBtn.setOnClickListener { sendQuestion() }

        val savedMessages = prefs.getStringSet("chat_history", emptySet()) ?: emptySet()
        savedMessages.forEach { json ->
            val obj = JSONObject(json)
            adapter.addMessage(ChatMessage(obj.getString("text"), obj.getBoolean("isUser")))
        }
        if (adapter.itemCount > 0) {
            chatRecycler.scrollToPosition(adapter.itemCount - 1)
        }

        findViewById<Button>(R.id.graph_btn).setOnClickListener {
            startActivity(Intent(this, GraphActivity::class.java))
        }
    }

    private fun sendQuestion() {
        val question = inputField.text.toString().trim()
        if (question.isEmpty()) return

        inputField.text.clear()
        adapter.addMessage(ChatMessage("Вы: $question", true))
        chatRecycler.scrollToPosition(adapter.itemCount - 1)

        progressBar.visibility = View.VISIBLE
        sendBtn.isEnabled = false

        currentJob = lifecycleScope.launch {
            val result = client.ask(question)
            result.onSuccess { response ->
                adapter.addMessage(ChatMessage("GhostGPT: $response", false))
            }.onFailure { error ->
                adapter.addMessage(ChatMessage("Ошибка: ${error.message}", false))
            }
            progressBar.visibility = View.GONE
            sendBtn.isEnabled = true
            chatRecycler.scrollToPosition(adapter.itemCount - 1)

            val prefs = getSharedPreferences("ghostgpt", MODE_PRIVATE)
            val history = adapter.getMessages().takeLast(20).map {
                JSONObject().put("text", it.text).put("isUser", it.isUser).toString()
            }.toSet()
            prefs.edit().putStringSet("chat_history", history).apply()
        }
    }

    override fun onDestroy() {
        currentJob?.cancel()
        super.onDestroy()
    }

    override fun onCreateOptionsMenu(menu: Menu?): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_settings -> {
                showSettingsDialog()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun showSettingsDialog() {
        val prefs = getSharedPreferences("ghostgpt", MODE_PRIVATE)
        val input = EditText(this).apply {
            setText("${prefs.getString("host", "192.168.1.100")}:${prefs.getInt("port", 8765)}")
        }
        AlertDialog.Builder(this)
            .setTitle("Адрес GhostGPT")
            .setView(input)
            .setPositiveButton("Сохранить") { _, _ ->
                val parts = input.text.toString().split(":").map { it.trim() }
                prefs.edit()
                    .putString("host", parts.getOrElse(0) { "192.168.1.100" })
                    .putInt("port", parts.getOrElse(1) { "8765" }.toIntOrNull() ?: 8765)
                    .apply()
                recreate()
            }
            .setNegativeButton("Отмена", null)
            .show()
    }
}
