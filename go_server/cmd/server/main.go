package main

import (
	"log"
	"net/http"
	"os"
	"time"
	"vpf11-user-api/internal/httpapi"
	"vpf11-user-api/internal/store"
)

func main() {
	path := os.Getenv("DATABASE_PATH")
	if path == "" {
		path = "users.db"
	}
	addr := os.Getenv("LISTEN_ADDR")
	if addr == "" {
		addr = "127.0.0.1:8080"
	}
	db, err := store.Open(path)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	server := &http.Server{Addr: addr, Handler: httpapi.New(db), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16384}
	log.Printf("listening on %s", addr)
	log.Fatal(server.ListenAndServe())
}
