package com.ghostgpt.companion

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

class AgentClient(private val baseUrl: String) {

    suspend fun ask(question: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val endpoint = URL("$baseUrl/api/agent/loop")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 10_000
            conn.readTimeout = 30_000
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true

            val payload = JSONObject().put("message", question).toString()
            conn.outputStream.use { it.write(payload.toByteArray(Charsets.UTF_8)) }

            val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
            val body = BufferedReader(InputStreamReader(stream)).use { it.readText() }

            if (conn.responseCode !in 200..299) {
                throw IllegalStateException("HTTP ${conn.responseCode}: $body")
            }

            val json = JSONObject(body)
            when {
                json.has("response") -> json.getString("response")
                json.has("message") -> json.getString("message")
                else -> body
            }
        }.recoverCatching { error ->
            when (error) {
                is SocketTimeoutException -> throw Exception("Сервер не отвечает (таймаут 30 сек)")
                else -> throw error
            }
        }
    }
}
