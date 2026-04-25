total = 0
for i in 0..<__ITER__ {
 pos = &message.indexOf(&marker)
 slice = &message.substring(&pos, &pos + &marker.length())
 total += &pos + &slice.length()
}
&total
