sum = 0
for i in 0..<__ITER__ {
 sum += &lookupMap.get("k" + (&i % 128))
}
&sum
