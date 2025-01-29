import {
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
  Menu as MenuIcon,
} from "@mui/icons-material";
import {
  AppBar,
  AppBarProps,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  styled,
  useTheme,
} from "@mui/material";
import { useState } from "react";
import { Outlet } from "react-router-dom";
import { pageList, useCurrentPage } from "./pages";

const drawerWidth = 240;

const Main = styled("main", { shouldForwardProp: (prop) => prop !== "open" })<{
  open?: boolean;
}>(({ theme, open }) => ({
  flexGrow: 1,
  padding: theme.spacing(3),
  transition: theme.transitions.create("margin", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  marginLeft: `-${drawerWidth}px`,
  ...(open && {
    transition: theme.transitions.create("margin", {
      easing: theme.transitions.easing.easeOut,
      duration: theme.transitions.duration.enteringScreen,
    }),
    marginLeft: 0,
  }),
}));

interface StyledAppBarProps extends AppBarProps {
  open?: boolean;
}

const StyledAppBar = styled(AppBar, {
  shouldForwardProp: (prop) => prop !== "open",
})<StyledAppBarProps>(({ theme, open }) => ({
  transition: theme.transitions.create(["margin", "width"], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  ...(open && {
    width: `calc(100% - ${drawerWidth}px)`,
    marginLeft: `${drawerWidth}px`,
    transition: theme.transitions.create(["margin", "width"], {
      easing: theme.transitions.easing.easeOut,
      duration: theme.transitions.duration.enteringScreen,
    }),
  }),
}));

const DrawerHeader = styled("div")(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  padding: theme.spacing(0, 1),
  // necessary for content to be below app bar
  ...theme.mixins.toolbar,
  justifyContent: "flex-end",
}));

export const Layout = () => {
  const currentPage = useCurrentPage();

  const theme = useTheme();
  const [open, setOpen] = useState(false);

  const handleDrawerOpen = () => setOpen(true);

  const handleDrawerClose = () => setOpen(false);

  // adapted from https://mui.com/material-ui/react-drawer/#persistent-drawer
  return (
    <Box sx={{ display: "flex" }}>
      <StyledAppBar position="fixed" open={open}>
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            onClick={handleDrawerOpen}
            edge="start"
            sx={{ mr: 2, ...(open && { display: "none" }) }}
          >
            <MenuIcon />
          </IconButton>

          <Typography variant="h6" noWrap component="div">
            {currentPage.title}
          </Typography>
        </Toolbar>
      </StyledAppBar>

      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: drawerWidth,
            boxSizing: "border-box",
          },
        }}
        variant="persistent"
        anchor="left"
        open={open}
      >
        <DrawerHeader>
          <IconButton onClick={handleDrawerClose}>
            {theme.direction === "ltr" ? (
              <ChevronLeftIcon />
            ) : (
              <ChevronRightIcon />
            )}
          </IconButton>
        </DrawerHeader>

        <Divider />

        <List>
          {pageList.map((page) => {
            const props: { href?: string } = {};
            if (currentPage !== page) {
              props.href = `#${page.path}`;
            }

            return (
              <ListItem key={page.id} disablePadding>
                <ListItemButton {...props} disableRipple>
                  <ListItemIcon>{page.icon}</ListItemIcon>
                  <ListItemText primary={page.title} />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
      </Drawer>

      <Main open={open}>
        <DrawerHeader />

        <Outlet />
      </Main>
    </Box>
  );
};
