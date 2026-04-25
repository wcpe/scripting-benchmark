package cn.altawk.test.scripting

import java.awt.Point
import java.util.LinkedHashMap
import java.util.regex.Pattern

const val SAMPLE_ITERATIONS_PROPERTY = "scripting.sampleIterations"
const val DEFAULT_SAMPLE_ITERATIONS = 2_000

private const val ITER_PLACEHOLDER = "__ITER__"

/** 跨引擎共享的测试场景；各引擎通过相同 id 加载对应语言版本的脚本样本。 */
val BENCHMARK_SCRIPT_CASES = listOf(
    // 基础控制流和算术。
    BenchmarkScriptCase("compute"),
    BenchmarkScriptCase("branching"),
    BenchmarkScriptCase("nested-loop"),

    // 集合、映射和字符串构造/访问。
    BenchmarkScriptCase("list-index"),
    BenchmarkScriptCase("list-build"),
    BenchmarkScriptCase("map-build"),
    BenchmarkScriptCase("string-build"),
    BenchmarkScriptCase("map-read", ::mapReadBindings),
    BenchmarkScriptCase("collection-transform", ::collectionTransformBindings),
    BenchmarkScriptCase("string-methods", ::stringMethodBindings),

    // 绑定变量表达式和常见工具类调用。
    BenchmarkScriptCase("variable-expression", ::variableExpressionBindings),
    BenchmarkScriptCase("regex-match", ::regexBindings),

    // 宿主 Java API 互操作。
    BenchmarkScriptCase("host-class-access", ::javaApiBindings),
    BenchmarkScriptCase("host-instance-field-read", ::javaApiBindings),
    BenchmarkScriptCase("host-static-field-read", ::javaApiBindings),
    BenchmarkScriptCase("host-instance-method-call", ::javaApiBindings),
    BenchmarkScriptCase("host-static-method-call", ::javaApiBindings),
    BenchmarkScriptCase("object-allocation"),
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

/** 宿主 Map 查询样本所需的共享变量。 */
private fun mapReadBindings(): MutableMap<String, Any?> = linkedMapOf(
    "lookupMap" to LinkedHashMap<String, Int>(128).apply {
        repeat(128) { index -> put("k$index", index * 3 + 1) }
    },
)

/** 集合转换样本所需的共享变量。 */
private fun collectionTransformBindings(): MutableMap<String, Any?> = linkedMapOf(
    "numbers" to ArrayList<Int>(128).apply {
        repeat(128) { index -> add(index * 2 + 1) }
    },
)

/** 字符串方法组合样本所需的共享变量。 */
private fun stringMethodBindings(): MutableMap<String, Any?> = linkedMapOf(
    "message" to "prefix-alpha-beta-marker-gamma-delta-suffix",
    "marker" to "marker",
)

/** 正则匹配样本所需的共享变量。 */
private fun regexBindings(): MutableMap<String, Any?> = linkedMapOf(
    "pattern" to Pattern.compile("item-(\\d+)-([a-z]+)"),
    "regexText" to "prefix item-42-alpha suffix item-73-beta",
)
