package cn.altawk.test.scripting

import java.awt.Point

const val SAMPLE_ITERATIONS_PROPERTY = "scripting.sampleIterations"
const val DEFAULT_SAMPLE_ITERATIONS = 2_000

private const val ITER_PLACEHOLDER = "__ITER__"

/** 跨引擎共享的测试场景；各引擎通过相同 id 加载对应语言版本的脚本样本。 */
val BENCHMARK_SCRIPT_CASES = listOf(
    BenchmarkScriptCase("compute"),
    BenchmarkScriptCase("branching"),
    BenchmarkScriptCase("nested-loop"),
    BenchmarkScriptCase("list-index"),
    BenchmarkScriptCase("list-build"),
    BenchmarkScriptCase("map-build"),
    BenchmarkScriptCase("string-build"),
    BenchmarkScriptCase("variable-expression", ::variableExpressionBindings),
    BenchmarkScriptCase("host-class-access", ::javaApiBindings),
    BenchmarkScriptCase("host-instance-field-read", ::javaApiBindings),
    BenchmarkScriptCase("host-static-field-read", ::javaApiBindings),
    BenchmarkScriptCase("host-instance-method-call", ::javaApiBindings),
    BenchmarkScriptCase("host-static-method-call", ::javaApiBindings),
)

/** 加载指定引擎在该场景下的样本；不存在时抛出明确错误。 */
fun BenchmarkScriptCase.sampleFor(adapter: ScriptEngineAdapter<*>): ScriptSample = sampleOrNull(adapter)
    ?: error("${adapter.engineName} 不支持脚本样本 $id，缺少资源文件 ${resourcePath(adapter)}")

private fun BenchmarkScriptCase.sampleOrNull(adapter: ScriptEngineAdapter<*>): ScriptSample? {
    val path = resourcePath(adapter)
    val content = BenchmarkScriptCase::class.java.getResource(path)?.readText() ?: return null
    return ScriptSample(
        path = path,
        content = content.replace(ITER_PLACEHOLDER, sampleIterations().toString()),
        bindingsFactory = bindingsFactory,
    )
}

private fun sampleIterations(): Int = System.getProperty(SAMPLE_ITERATIONS_PROPERTY)
    ?.toIntOrNull()
    ?.takeIf { it > 0 }
    ?: DEFAULT_SAMPLE_ITERATIONS

private fun BenchmarkScriptCase.resourcePath(adapter: ScriptEngineAdapter<*>): String {
    return "/samples/${adapter.sampleDirectory}/$id${adapter.sampleExtension}"
}

/** Java/宿主 API 访问类样本所需的共享变量。 */
private fun javaApiBindings(): MutableMap<String, Any?> = linkedMapOf(
    "integerClass" to Int::class.javaObjectType,
    "mathClass" to Math::class.java,
    "point" to Point(7, 11),
    "text" to "benchmark-mark",
)

/** 复杂变量表达式样本所需的共享变量。 */
private fun variableExpressionBindings(): MutableMap<String, Any?> = linkedMapOf(
    "base" to 17,
    "multiplier" to 29,
    "modulus" to 7,
    "offset" to 43,
    "divisor" to 3,
    "bias" to 5,
)
