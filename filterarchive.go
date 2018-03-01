package main

import (
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/catapult-project/catapult/web_page_replay_go/src/webpagereplay"
	"github.com/urfave/cli"
)

// Returns true if the request host is in the hostnameList and false otherwsie
func reqEnabled(req *http.Request, hostnames map[string]bool) bool {

	return hostnames[req.Host]
}

func filterArchive(c *cli.Context) {
	fmt.Println("Running filterarchive", c.Args().Get(0), c.Args().Get(1), c.Args().Get(2))

	// Format hostnameList csv into a map for fast membership check
	hostnameList := strings.Split(c.Args().Get(2), ",")
	hostnameMap := make(map[string]bool)
	for _, hostname := range hostnameList {
		hostnameMap[hostname] = true
	}

	// Load archive
	archive, err := webpagereplay.OpenArchive(c.Args().Get(0))
	if err != nil {
		fmt.Println("Error loading the inputArchive:", err)
		os.Exit(1)
	}

	// Filter archive
	newArchive, err := archive.Edit(func(req *http.Request, resp *http.Response) (*http.Request, *http.Response, error) {
		if reqEnabled(req, hostnameMap) {
			return req, resp, nil
		}
		return nil, nil, nil
	})
	if err != nil {
		fmt.Println("Error filtering the archive:", err)
		os.Exit(1)
	}

	// Write new archive
	newArchiveFile, err := os.OpenFile(c.Args().Get(1), os.O_WRONLY|os.O_CREATE, os.FileMode(0777))
	if err != nil {
		fmt.Println("Error opening output file:", err)
		os.Exit(1)
	}
	serErr := newArchive.Serialize(newArchiveFile)
	closeErr := newArchiveFile.Close()
	if serErr != nil {
		fmt.Println("Error writing the archive to the new file:", serErr)
		os.Exit(1)
	}
	if closeErr != nil {
		fmt.Println("Error closing the new file", closeErr)
		os.Exit(1)
	}
}

func main() {
	app := cli.NewApp()
	app.Name = "filterarchive"
	app.Usage = "Filters a WebPageReplay archive file"
	app.ArgsUsage = "inputArchive outputArchive hostnameList"
	app.Action = filterArchive
	app.HideVersion = true
	app.Version = ""

	app.Run(os.Args)
}
