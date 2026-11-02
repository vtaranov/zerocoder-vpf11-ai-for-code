package httpapi

import (
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"unicode/utf8"
	"vpf11-user-api/internal/store"
)

func respond(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
func parseID(raw string) (int64, bool) {
	if len(raw) == 0 || len(raw) > 19 || strings.Trim(raw, "0123456789") != "" {
		return 0, false
	}
	id, err := strconv.ParseInt(raw, 10, 64)
	return id, err == nil && id > 0
}
func New(s *store.Store) http.Handler {
	var activeMu sync.Mutex
	active := make([]int64, 0, 3)
	mux := http.NewServeMux()
	mux.HandleFunc("POST /adduser", func(w http.ResponseWriter, r *http.Request) {
		media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
		if err != nil || media != "application/json" {
			respond(w, 400, map[string]string{"error": "invalid_json"})
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 16384)
		raw, err := io.ReadAll(r.Body)
		if err != nil {
			var tooLarge *http.MaxBytesError
			if errors.As(err, &tooLarge) {
				respond(w, 413, map[string]string{"error": "request_too_large"})
			} else {
				respond(w, 400, map[string]string{"error": "invalid_json"})
			}
			return
		}
		var input map[string]json.RawMessage
		if !utf8.Valid(raw) || !json.Valid(raw) {
			respond(w, 400, map[string]string{"error": "invalid_json"})
			return
		}
		if json.Unmarshal(raw, &input) != nil || input == nil {
			respond(w, 400, map[string]string{"error": "invalid_name"})
			return
		}
		var name string
		v, found := input["name"]
		if len(input) != 1 || !found || json.Unmarshal(v, &name) != nil {
			respond(w, 400, map[string]string{"error": "invalid_name"})
			return
		}
		name = strings.TrimSpace(name)
		if name == "" || len(name) > 200 || strings.ContainsRune(name, 0) {
			respond(w, 400, map[string]string{"error": "invalid_name"})
			return
		}
		u, err := s.Add(r.Context(), name)
		if err != nil {
			respond(w, 500, map[string]string{"error": "internal_error"})
			return
		}
		respond(w, 201, map[string]any{"status": "ok", "id": u.ID, "name": u.Name})
	})
	mux.HandleFunc("GET /user/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseID(r.PathValue("id"))
		if !ok {
			respond(w, 404, map[string]string{"error": "not_found"})
			return
		}
		u, err := s.Get(r.Context(), id)
		if errors.Is(err, sql.ErrNoRows) {
			respond(w, 404, map[string]string{"error": "not_found"})
			return
		}
		if err != nil {
			respond(w, 500, map[string]string{"error": "internal_error"})
			return
		}
		respond(w, 200, u)
	})
	mux.HandleFunc("POST /activate/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, ok := parseID(r.PathValue("id"))
		if !ok {
			respond(w, 404, map[string]string{"error": "not_found"})
			return
		}
		_, err := s.Get(r.Context(), id)
		if errors.Is(err, sql.ErrNoRows) {
			respond(w, 404, map[string]string{"error": "not_found"})
			return
		}
		if err != nil {
			respond(w, 500, map[string]string{"error": "internal_error"})
			return
		}
		activeMu.Lock()
		active = append(active, id)
		if len(active) > 3 {
			active = active[len(active)-3:]
		}
		snapshot := append([]int64(nil), active...)
		activeMu.Unlock()
		respond(w, 200, map[string]any{"status": "ok", "active": snapshot})
	})
	mux.HandleFunc("GET /slow", func(w http.ResponseWriter, r *http.Request) {
		const n int64 = 1_000_000
		total := 4950 * n * (n - 1) / 2
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		_, _ = w.Write([]byte(strconv.FormatInt(total, 10)))
	})
	mux.HandleFunc("GET /wrong", func(w http.ResponseWriter, r *http.Request) {
		respond(w, 500, map[string]string{"error": "demonstration_error"})
	})
	return mux
}
