import { Card, CardContent, FormControl, Icon, TextField } from "@mui/material";
import { LoadingButton } from "@mui/lab";
import React, { useEffect, useState } from "react";
import "./styles.css";
import { useSearchParams } from "react-router-dom";
import axios from "axios";
import ReactCardFlip from "react-card-flip";
import GppBadOutlinedIcon from "@mui/icons-material/GppBadOutlined";
import VerifiedUserOutlinedIcon from "@mui/icons-material/VerifiedUserOutlined";

const mailRegex = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$/i;

const Auth = () => {
  const [mail, setMail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [flipped, setFilpped] = useState(false);
  const [signSuccess, setSignSuccess] = useState(false);

  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => console.log("host-ip", process.env.REACT_APP_HOST_IP));

  useEffect(() => {
    let timer1;
    if (signSuccess) {
      timer1 = setTimeout(
        () => (window.location.href = "https://google.com"),
        2500
      );
    }

    return () => {
      clearTimeout(timer1);
    };
  }, [signSuccess]);

  const handleChange = (event) => {
    if (error) {
      setError("");
    }
    setMail(event.target.value);
  };

  const handleSubmit = () => {
    const ip = searchParams.get("ip");
    const isValid = !!mail && mailRegex.test(mail);
    if (!isValid) {
      setError(mail ? "Email inválido" : "Campo requerido");
      return;
    }

    setLoading(true);

    axios
      .post(
        `http://${process.env.REACT_APP_HOST_IP || "localhost"}:3000/submit`,
        { ip, mail }
      )
      .then((response) => {
        //redirect to success
        setSignSuccess(true);
        setFilpped(true);
        setLoading(false);
      })
      .catch((error) => {
        //redirect to failure
        setSignSuccess(false);
        setFilpped(true);
        setLoading(false);
      });
  };

  return (
    <div className="main-container">
      <ReactCardFlip isFlipped={flipped}>
        <Card>
          <CardContent className="card-content">
            <div className="title-container">
              <img src={require("./uca_logo.png")} className="logo" alt="" />
              <span className="form-title">
                Ingresá tu email para seguir navegando
              </span>
            </div>
            <div className="form-container">
              <FormControl className="form-control">
                <TextField
                  id="outlined-basic"
                  variant="outlined"
                  value={mail}
                  onChange={handleChange}
                  label="Email"
                  error={!!error}
                  helperText={error}
                />
              </FormControl>
            </div>
            <LoadingButton
              loading={loading}
              variant="contained"
              onClick={handleSubmit}
              className="button"
            >
              Ingresar
            </LoadingButton>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="card-content">
            {signSuccess ? (
              <VerifiedUserOutlinedIcon
                sx={{ fontSize: 150, color: "darkgreen" }}
                className="icon"
              />
            ) : (
              <GppBadOutlinedIcon
                sx={{ fontSize: 150, color: "darkred" }}
                className="icon"
              />
            )}
            <span className="card-title">
              {signSuccess ? "¡Éxito!" : "Error"}
            </span>
            <span className="card-subtitle">
              {signSuccess
                ? "Muchas gracias por registrarte. Disfrutá tu navegación :)"
                : "Hubo un error de registro. Cerrá el navegador e intentá nuevamente."}
            </span>
          </CardContent>
        </Card>
      </ReactCardFlip>
    </div>
  );
};

export default Auth;
