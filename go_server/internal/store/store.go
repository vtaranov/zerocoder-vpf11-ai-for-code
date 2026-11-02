package store

import (
	"context"
	"database/sql"
	_ "modernc.org/sqlite"
)

type Store struct{ db *sql.DB }
type User struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

func Open(path string) (*Store, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	if _, err = db.Exec(`CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)`); err != nil {
		db.Close()
		return nil, err
	}
	return &Store{db}, nil
}
func (s *Store) Close() error { return s.db.Close() }
func (s *Store) Add(ctx context.Context, name string) (User, error) {
	res, err := s.db.ExecContext(ctx, `INSERT INTO users(name) VALUES (?)`, name)
	if err != nil {
		return User{}, err
	}
	id, err := res.LastInsertId()
	return User{ID: id, Name: name}, err
}
func (s *Store) Get(ctx context.Context, id int64) (User, error) {
	var u User
	err := s.db.QueryRowContext(ctx, `SELECT id, name FROM users WHERE id = ?`, id).Scan(&u.ID, &u.Name)
	return u, err
}
