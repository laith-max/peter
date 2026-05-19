package main

import (
	"flag"
	"fmt"
	"os"
	"runtime"
)

var version = "dev"

func main() {
	showVersion := flag.Bool("version", false, "print version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Printf("peter %s %s/%s (%s)\n", version, runtime.GOOS, runtime.GOARCH, runtime.Version())
		return
	}

	fmt.Fprintln(os.Stderr, "peter: no command specified")
	flag.Usage()
	os.Exit(2)
}
