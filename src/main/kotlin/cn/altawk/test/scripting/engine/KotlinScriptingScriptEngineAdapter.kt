package cn.altawk.test.scripting.engine

import cn.altawk.test.scripting.ScriptEngineAdapter
import cn.altawk.test.scripting.ScriptSample
import java.lang.reflect.Constructor
import java.lang.reflect.Field
import java.lang.reflect.InvocationTargetException
import kotlin.script.experimental.api.CompiledScript as KotlinCompiledScript
import kotlin.script.experimental.api.EvaluationResult
import kotlin.script.experimental.api.KotlinType
import kotlin.script.experimental.api.ResultValue
import kotlin.script.experimental.api.ResultWithDiagnostics
import kotlin.script.experimental.api.ScriptCompilationConfiguration
import kotlin.script.experimental.api.ScriptDiagnostic
import kotlin.script.experimental.api.ScriptEvaluationConfiguration
import kotlin.script.experimental.api.SourceCode
import kotlin.script.experimental.api.providedProperties
import kotlin.script.experimental.host.toScriptSource
import kotlin.script.experimental.jvm.dependenciesFromCurrentContext
import kotlin.script.experimental.jvm.impl.KJvmCompiledScript
import kotlin.script.experimental.jvm.impl.getOrCreateActualClassloader
import kotlin.script.experimental.jvm.jvm
import kotlin.script.experimental.jvmhost.BasicJvmScriptingHost

/** Kotlin Scripting 适配器；使用 BasicJvmScriptingHost 编译/执行 .kts 样本。 */
object KotlinScriptingScriptEngineAdapter : ScriptEngineAdapter<KotlinPreparedScript> {

    override val engineName: String = "KotlinScripting"
    override val sampleDirectory: String = "kotlin"
    override val sampleExtension: String = ".kts"

    override fun compile(sample: ScriptSample): KotlinPreparedScript {
        val bindings = sample.bindingsFactory()
        val compiled = BenchmarkKtsHost.compile(
            sample.toSourceCode(),
            benchmarkCompilationConfiguration(bindings),
        ).valueOrThrow()
        return KotlinPreparedScript(compiled, benchmarkEvaluationConfiguration(bindings))
    }

    override fun runCompiled(compiled: KotlinPreparedScript): Any? {
        return BenchmarkKtsHost.evalCompiled(compiled.script, compiled.evaluationConfiguration)
            .valueOrThrow()
            .returnValue
            .unwrap()
    }

    override fun interpret(sample: ScriptSample): Any? {
        val bindings = sample.bindingsFactory()
        return BenchmarkKtsHost.evalSource(
            sample.toSourceCode(),
            benchmarkCompilationConfiguration(bindings),
            benchmarkEvaluationConfiguration(bindings),
        ).valueOrThrow()
            .returnValue
            .unwrap()
    }
}

/**
 * Kotlin Scripting 优化适配器。
 *
 * compile 阶段仍保留 `wholeClasspath = true`，但额外完成脚本类加载、构造器/返回字段解析与参数数组构建；
 * compiledExecution 阶段绕过 BasicJvmScriptEvaluator，直接实例化脚本类并读取返回值。
 */
object KotlinScriptingOptimizedScriptEngineAdapter : ScriptEngineAdapter<KotlinOptimizedPreparedScript> {

    override val engineName: String = "KotlinScriptingOptimized"
    override val sampleDirectory: String = "kotlin"
    override val sampleExtension: String = ".kts"

    override fun compile(sample: ScriptSample): KotlinOptimizedPreparedScript {
        val bindings = sample.bindingsFactory()
        val compilationConfiguration = benchmarkCompilationConfiguration(bindings)
        val evaluationConfiguration = benchmarkEvaluationConfiguration(bindings)
        val script = BenchmarkKtsHost.compile(sample.toSourceCode(), compilationConfiguration)
            .valueOrThrow()
            .asKJvmCompiledScript()
        require(script.otherScripts.isEmpty()) { "Kotlin 优化适配器暂不支持 imported scripts" }
        val classLoader = script.getOrCreateActualClassloader(evaluationConfiguration)
        val scriptClass = classLoader.loadClass(script.scriptClassFQName)
        val resultField = script.resultField?.first?.let { fieldName ->
            scriptClass.getDeclaredField(fieldName).apply { isAccessible = true }
        }

        return KotlinOptimizedPreparedScript(
            classLoader = classLoader,
            constructor = scriptClass.constructors.single(),
            constructorArgs = bindings.toConstructorArgs(),
            resultField = resultField,
        )
    }

    override fun runCompiled(compiled: KotlinOptimizedPreparedScript): Any? {
        val currentThread = Thread.currentThread()
        val previousClassLoader = currentThread.contextClassLoader
        currentThread.contextClassLoader = compiled.classLoader
        return try {
            val instance = try {
                compiled.constructor.newInstance(*compiled.constructorArgs)
            } catch (e: InvocationTargetException) {
                throw (e.targetException ?: e)
            }
            if (compiled.resultField != null) compiled.resultField.get(instance) else Unit
        } finally {
            currentThread.contextClassLoader = previousClassLoader
        }
    }

    override fun interpret(sample: ScriptSample): Any? {
        return KotlinScriptingScriptEngineAdapter.interpret(sample)
    }
}

data class KotlinPreparedScript(
    val script: KotlinCompiledScript,
    val evaluationConfiguration: ScriptEvaluationConfiguration,
)

data class KotlinOptimizedPreparedScript(
    val classLoader: ClassLoader,
    val constructor: Constructor<*>,
    val constructorArgs: Array<Any?>,
    val resultField: Field?,
)

private object BenchmarkKtsHost : BasicJvmScriptingHost() {

    fun compile(
        script: SourceCode,
        compilationConfiguration: ScriptCompilationConfiguration,
    ): ResultWithDiagnostics<KotlinCompiledScript> = runInCoroutineContext {
        compiler(script, compilationConfiguration)
    }

    fun evalCompiled(
        compiled: KotlinCompiledScript,
        evaluationConfiguration: ScriptEvaluationConfiguration,
    ): ResultWithDiagnostics<EvaluationResult> = runInCoroutineContext {
        evaluator(compiled, evaluationConfiguration)
    }

    fun evalSource(
        script: SourceCode,
        compilationConfiguration: ScriptCompilationConfiguration,
        evaluationConfiguration: ScriptEvaluationConfiguration,
    ): ResultWithDiagnostics<EvaluationResult> = runInCoroutineContext {
        eval(script, compilationConfiguration, evaluationConfiguration)
    }
}

private fun ScriptSample.toSourceCode(): SourceCode {
    return content.toScriptSource(path.substringAfterLast('/'))
}

private fun benchmarkCompilationConfiguration(bindings: Map<String, Any?>): ScriptCompilationConfiguration {
    return ScriptCompilationConfiguration {
        jvm {
            dependenciesFromCurrentContext(wholeClasspath = true)
        }
        if (bindings.isNotEmpty()) {
            providedProperties(bindings.mapValues { (_, value) -> value.toKotlinType() })
        }
    }
}

private fun benchmarkEvaluationConfiguration(bindings: Map<String, Any?>): ScriptEvaluationConfiguration {
    return ScriptEvaluationConfiguration {
        if (bindings.isNotEmpty()) {
            providedProperties(bindings)
        }
    }
}

private fun Any?.toKotlinType(): KotlinType = KotlinType(this?.let { it::class } ?: Any::class)

private fun KotlinCompiledScript.asKJvmCompiledScript(): KJvmCompiledScript {
    return this as? KJvmCompiledScript
        ?: error("Kotlin 优化适配器仅支持 JVM 编译产物，实际类型: ${this::class.qualifiedName}")
}

private fun Map<String, Any?>.toConstructorArgs(): Array<Any?> = values.toTypedArray()

private fun ResultValue.unwrap(): Any? {
    return when (this) {
        is ResultValue.Value -> value
        is ResultValue.Unit -> Unit
        is ResultValue.Error -> error("Kotlin 脚本执行失败: $error")
        is ResultValue.NotEvaluated -> error("Kotlin 脚本未执行")
    }
}

private fun <T> ResultWithDiagnostics<T>.valueOrThrow(): T {
    return when (this) {
        is ResultWithDiagnostics.Success -> value
        is ResultWithDiagnostics.Failure -> error(renderDiagnostics(reports))
    }
}

private fun renderDiagnostics(reports: List<ScriptDiagnostic>): String {
    return reports.joinToString(separator = "\n") { report ->
        buildString {
            append(report.severity)
            append(": ")
            append(report.message)
            report.exception?.let {
                append(" (")
                append(it::class.qualifiedName)
                append(": ")
                append(it.message)
                append(')')
            }
        }
    }
}
