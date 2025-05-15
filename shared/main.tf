resource "docker_image" "wordpress" {
 name = "wordpress:latest"
}

resource "docker_container" "wordpress" {
 name  = "wordpress-container"
 image = docker_image.wordpress.name
 ports {
 internal = 80
 external = 8080
 }
 depends_on = [docker_container.mysql]
}

resource "docker_image" "mysql" {
 name = "mysql:latest"
}

resource "docker_container" "mysql" {
 name  = "mysql-container"
 image = docker_image.mysql.name
 environment = ["MYSQL_ROOT_PASSWORD=rootpassword"]
 ports {
 internal = 3306
 external = 3306
 }
}